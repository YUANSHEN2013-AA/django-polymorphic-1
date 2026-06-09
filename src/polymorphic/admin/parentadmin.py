"""
The parent admin displays the list view of the base model.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Generic, cast

from django.contrib import admin
from django.contrib.admin.helpers import AdminErrorList, AdminForm
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.db import models
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.template.response import TemplateResponse
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _
from typing_extensions import TypeVar

from polymorphic.models import PolymorphicModel
from polymorphic.query import PolymorphicQuerySet
from polymorphic.utils import get_base_polymorphic_model

from .forms import PolymorphicModelChoiceForm

_ModelT = TypeVar("_ModelT", bound=PolymorphicModel, default=PolymorphicModel)

if TYPE_CHECKING:
    _ModelAdminBase = admin.ModelAdmin[_ModelT]
else:
    _ModelAdminBase = admin.ModelAdmin


# Session key prefixes used to persist user preferences.
_SESSION_FAVORITES = "polymorphic_favorites"
_SESSION_RECENT = "polymorphic_recent"
_MAX_RECENT_ITEMS = 5


class RegistrationClosed(RuntimeError):
    "The admin model can't be registered anymore at this point."


class ChildAdminNotRegistered(RuntimeError):
    "The admin site for the model is not registered."


class PolymorphicParentModelAdmin(_ModelAdminBase, Generic[_ModelT]):
    """
    A admin interface that can displays different change/delete pages, depending on the polymorphic model.
    To use this class, one attribute need to be defined:

    * :attr:`child_models` should be a list models.

    Alternatively, the following methods can be implemented:

    * :func:`get_child_models` should return a list of models.
    * optionally, :func:`get_child_type_choices` can be overwritten to refine the choices for the add dialog.

    This class needs to be inherited by the model admin base class that is registered in the site.
    The derived models should *not* register the ModelAdmin, but instead it should be returned by :func:`get_child_models`.
    """

    #: The base model that the class uses (auto-detected if not set explicitly)
    base_model: type[models.Model] | None = None

    #: The child models that should be displayed
    child_models: list[type[models.Model]] | None = None

    #: Whether the list should be polymorphic too, leave to ``False`` to optimize
    polymorphic_list = False

    add_type_template = None
    add_type_form = PolymorphicModelChoiceForm

    #: Whether the "add type" dialog uses the new rich picker (with search,
    #: favorites, recent items and categories). When ``True`` the list of
    #: child types is loaded asynchronously via JSON. When ``False`` the
    #: classic radio-list UI is used (kept for backwards compatibility).
    polymorphic_type_picker = True

    #: The regular expression to filter the primary key in the URL.
    #: This accepts only numbers as defensive measure against catch-all URLs.
    #: If your primary key consists of string values, update this regular expression.
    pk_regex = r"(\d+|__fk__)"

    def __init__(self, model: type[_ModelT], admin_site: Any, *args: Any, **kwargs: Any) -> None:
        super().__init__(model, admin_site, *args, **kwargs)
        self._is_setup = False

        if self.base_model is None:
            self.base_model = get_base_polymorphic_model(model)

    def _lazy_setup(self):
        if self._is_setup:
            return

        self._child_models = self.get_child_models()

        # Make absolutely sure that the child models don't use the old 0.9 format,
        # as of polymorphic 1.4 this deprecated configuration is no longer supported.
        # Instead, register the child models in the admin too.
        if self._child_models and not issubclass(self._child_models[0], models.Model):
            raise ImproperlyConfigured(
                "Since django-polymorphic 1.4, the `child_models` attribute "
                "and `get_child_models()` method should be a list of models only.\n"
                "The model-admin class should be registered in the regular Django admin."
            )

        self._child_admin_site = self.admin_site
        self._is_setup = True

    # ------------------------------------------------------------------
    # Child-type discovery / meta data
    # ------------------------------------------------------------------
    def get_child_models(self):
        """
        Return the derived model classes which this admin should handle.
        This should return a list of tuples, exactly like :attr:`child_models` is.

        The model classes can be retrieved as ``base_model.__subclasses__()``,
        a setting in a config file, or a query of a plugin registration system at your option
        """
        if self.child_models is None:
            raise NotImplementedError("Implement get_child_models() or child_models")

        return self.child_models

    def get_child_type_choices(self, request, action):
        """
        Return a list of polymorphic types for which the user has the permission to perform the given action.
        """
        self._lazy_setup()
        content_types = ContentType.objects.get_for_models(
            *self.get_child_models(), for_concrete_models=False
        )

        choices = []
        for model, ct in content_types.items():
            perm_function_name = f"has_{action}_permission"
            model_admin = self._get_real_admin_by_model(model)
            perm_function = getattr(model_admin, perm_function_name)
            if not perm_function(request):
                continue
            choices.append((ct.id, force_str(model._meta.verbose_name)))
        return choices

    def get_child_type_data(self, request, action: str = "add") -> list[dict[str, Any]]:
        """
        Return a list of dicts describing every available child type.

        Each dict contains:

        - ``ct_id`` (int)             : content type id
        - ``name`` (str)              : human readable name (verbose_name)
        - ``model_key`` (str)         : ``app_label.model_name`` identifier
        - ``category`` (str)          : category label used to group items
        - ``search_terms`` (list[str]): additional tokens used for searching
        - ``description`` (str)       : optional one-line description

        The list is sorted by (category, name) in a deterministic fashion.
        """
        self._lazy_setup()
        content_types = ContentType.objects.get_for_models(
            *self.get_child_models(), for_concrete_models=False
        )

        items: list[dict[str, Any]] = []
        for model, ct in content_types.items():
            perm_function_name = f"has_{action}_permission"
            model_admin = self._get_real_admin_by_model(model)
            perm_function = getattr(model_admin, perm_function_name)
            if not perm_function(request):
                continue

            items.append(
                {
                    "ct_id": ct.id,
                    "name": force_str(model._meta.verbose_name),
                    "model_key": f"{model._meta.app_label}.{model._meta.model_name}",
                    "category": self._get_child_type_category(model, model_admin),
                    "search_terms": list(self._get_child_type_search_terms(model, model_admin)),
                    "description": self._get_child_type_description(model, model_admin),
                }
            )

        items.sort(key=lambda item: (item["category"].lower(), item["name"].lower()))
        return items

    # -- overridable hooks -----------------------------------------------

    def _get_child_type_category(self, model, model_admin) -> str:
        category = getattr(model_admin, "polymorphic_category", None)
        if category:
            return force_str(category)
        if getattr(model._meta, "app_config", None) is not None:
            return force_str(model._meta.app_config.verbose_name)
        return force_str(model._meta.app_label)

    def _get_child_type_search_terms(self, model, model_admin) -> list[str]:
        terms: list[str] = [
            model._meta.object_name,
            model._meta.model_name,
            force_str(model._meta.verbose_name),
        ]
        extra = getattr(model_admin, "polymorphic_search_terms", None)
        if extra:
            terms.extend(str(t) for t in extra if t)
        return terms

    def _get_child_type_description(self, model, model_admin) -> str:
        desc = getattr(model_admin, "polymorphic_description", None)
        if desc:
            return force_str(desc)
        return ""

    # Public aliases that can be overridden freely by subclasses.
    get_child_type_category = _get_child_type_category
    get_child_type_search_terms = _get_child_type_search_terms
    get_child_type_description = _get_child_type_description

    # ------------------------------------------------------------------
    # Favorites / recent-items storage (session backed)
    # ------------------------------------------------------------------
    def _favorites_session_key(self) -> str:
        assert self.base_model is not None
        opts = self.base_model._meta
        return f"{_SESSION_FAVORITES}_{opts.app_label}_{opts.model_name}"

    def _recent_session_key(self) -> str:
        assert self.base_model is not None
        opts = self.base_model._meta
        return f"{_SESSION_RECENT}_{opts.app_label}_{opts.model_name}"

    def get_favorites(self, request) -> list[str]:
        """Return the list of favorite ``model_key`` s saved for the current user."""
        return list(request.session.get(self._favorites_session_key(), []) or [])

    def set_favorites(self, request, favorites: list[str]) -> None:
        request.session[self._favorites_session_key()] = list(favorites)

    def get_recent(self, request) -> list[str]:
        """Return the list of recently used ``model_key`` s for the current user."""
        return list(request.session.get(self._recent_session_key(), []) or [])

    def record_recent(self, request, model_key: str) -> None:
        """Promote ``model_key`` to the top of the recent-items list."""
        recent = [k for k in self.get_recent(request) if k != model_key]
        recent.insert(0, model_key)
        request.session[self._recent_session_key()] = recent[:_MAX_RECENT_ITEMS]

    # ------------------------------------------------------------------
    # Internal helpers for model → admin resolution
    # ------------------------------------------------------------------
    def _get_real_admin(self, object_id, super_if_self=True):
        try:
            obj = (
                self.model.objects.non_polymorphic().values("polymorphic_ctype").get(pk=object_id)
            )
        except self.model.DoesNotExist:
            raise Http404
        return self._get_real_admin_by_ct(obj["polymorphic_ctype"], super_if_self=super_if_self)

    def _get_real_admin_by_ct(self, ct_id, super_if_self=True):
        try:
            ct = ContentType.objects.get_for_id(ct_id)
        except ContentType.DoesNotExist as e:
            raise Http404(e)  # Handle invalid GET parameters

        model_class = ct.model_class()
        if not model_class:
            # Handle model deletion
            app_label, model = ct.natural_key()
            raise Http404(f"No model found for '{app_label}.{model}'.")

        return self._get_real_admin_by_model(model_class, super_if_self=super_if_self)

    def _get_real_admin_by_model(self, model_class, super_if_self=True):
        # In case of a ?ct_id=### parameter, the view is already checked for permissions.
        # Hence, make sure this is a derived object, or risk exposing other admin interfaces.
        if model_class not in self._child_models:
            raise PermissionDenied(
                f"Invalid model '{model_class}', it must be registered as child model."
            )

        try:
            # HACK: the only way to get the instance of an model admin,
            # is to read the registry of the AdminSite.
            real_admin = self._child_admin_site._registry[model_class]
        except KeyError:
            raise ChildAdminNotRegistered(
                f"No child admin site was registered for a '{model_class}' model."
            )

        if super_if_self and real_admin is self:
            return super()
        else:
            return real_admin

    # ------------------------------------------------------------------
    # Views
    # ------------------------------------------------------------------
    def get_queryset(self, request):
        # optimize the list display.
        qs = cast(PolymorphicQuerySet, super().get_queryset(request))
        if not self.polymorphic_list:
            qs = qs.non_polymorphic()
        return qs

    def add_view(self, request, form_url="", extra_context=None):
        """Redirect the add view to the real admin."""
        ct_id = int(request.GET.get("ct_id", 0))
        if not ct_id:
            # Display choices
            return self.add_type_view(request)
        else:
            real_admin = self._get_real_admin_by_ct(ct_id)
            # rebuild form_url, otherwise libraries below will override it.
            # Preserve popup-related parameters to ensure popup functionality works
            # correctly even after validation errors (issue #612)
            form_url = add_preserved_filters(
                {
                    "preserved_filters": request.GET.urlencode(),
                    "opts": self.model._meta,
                },
                form_url,
            )
            # Track the chosen child type as recently used.
            opts = real_admin.model._meta
            model_key = f"{opts.app_label}.{opts.model_name}"
            self.record_recent(request, model_key)
            return real_admin.add_view(request, form_url, extra_context)

    def change_view(self, request, object_id, *args, **kwargs):
        """Redirect the change view to the real admin."""
        real_admin = self._get_real_admin(object_id)
        return real_admin.change_view(request, object_id, *args, **kwargs)

    def changeform_view(self, request, object_id=None, *args, **kwargs):
        # The `changeform_view` is available as of Django 1.7, combining the add_view and change_view.
        # As it is directly called by django-reversion, this method is also overwritten to make sure it
        # also redirects to the child admin.
        if object_id:
            real_admin = self._get_real_admin(object_id)
            return real_admin.changeform_view(request, object_id, *args, **kwargs)
        else:
            # Add view. As it should already be handled via `add_view`, this means something custom is done here!
            return super().changeform_view(request, object_id, *args, **kwargs)

    def history_view(self, request, object_id, extra_context=None):
        """Redirect the history view to the real admin."""
        real_admin = self._get_real_admin(object_id)
        return real_admin.history_view(request, object_id, extra_context=extra_context)

    def delete_view(self, request, object_id, extra_context=None):
        """Redirect the delete view to the real admin."""
        real_admin = self._get_real_admin(object_id)
        return real_admin.delete_view(request, object_id, extra_context)

    # ------------------------------------------------------------------
    # URL routing
    # ------------------------------------------------------------------
    def get_urls(self):
        """
        Expose the custom URLs for the subclasses and the URL resolver.
        """
        from django.urls import path

        urls = super().get_urls()

        # At this point all admin code needs to be known.
        self._lazy_setup()

        app_label = self.model._meta.app_label
        model_name = self.model._meta.model_name
        custom_urls = [
            path(
                "child-types.json",
                self.admin_site.admin_view(self.child_types_json_view),
                name=f"{app_label}_{model_name}_child_types",
            ),
            path(
                "favorites/",
                self.admin_site.admin_view(self.favorites_view),
                name=f"{app_label}_{model_name}_favorites",
            ),
        ]
        return custom_urls + urls

    # ------------------------------------------------------------------
    # JSON endpoints for the rich type picker
    # ------------------------------------------------------------------
    def child_types_json_view(self, request):
        """Return a JSON payload describing available child types."""
        if not self.has_add_permission(request):
            raise PermissionDenied

        self._lazy_setup()
        items = self.get_child_type_data(request, action="add")

        favorites = set(self.get_favorites(request))
        recent = self.get_recent(request)

        data_items = []
        for item in items:
            data_items.append(
                {
                    **item,
                    "is_favorite": item["model_key"] in favorites,
                    "is_recent": item["model_key"] in recent,
                }
            )

        categories = sorted({item["category"] for item in items})
        return JsonResponse(
            {
                "items": data_items,
                "categories": categories,
                "favorites": list(favorites),
                "recent": recent,
            }
        )

    def favorites_view(self, request):
        """Toggle (add/remove) a favorite for the current user (POST)."""
        if not self.has_add_permission(request):
            raise PermissionDenied

        if request.method != "POST":
            return HttpResponse(status=405)

        try:
            body = json.loads(request.body)
        except (ValueError, json.JSONDecodeError):
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        action = body.get("action")
        model_key = body.get("model_key")
        if not model_key:
            return JsonResponse({"error": "missing model_key"}, status=400)

        # Validate the key corresponds to an allowed child type.
        allowed = {item["model_key"] for item in self.get_child_type_data(request, action="add")}
        if model_key not in allowed:
            return JsonResponse({"error": "unknown model"}, status=400)

        favorites = self.get_favorites(request)
        if action == "add":
            if model_key not in favorites:
                favorites.append(model_key)
        elif action == "remove":
            favorites = [k for k in favorites if k != model_key]
        else:
            return JsonResponse({"error": "unknown action"}, status=400)

        self.set_favorites(request, favorites)
        return JsonResponse({"favorites": favorites})

    # ------------------------------------------------------------------
    # add-type view (rendering)
    # ------------------------------------------------------------------
    def add_type_view(self, request, form_url=""):
        """
        Display a choice form to select which page type to add.
        """
        if not self.has_add_permission(request):
            raise PermissionDenied

        extra_qs = ""
        if request.META["QUERY_STRING"]:
            # QUERY_STRING is bytes in Python 3, using force_str() to decode it as string.
            # See QueryDict how Django deals with that.
            extra_qs = f"&{force_str(request.META['QUERY_STRING'])}"

        choices = self.get_child_type_choices(request, "add")
        if len(choices) == 0:
            raise PermissionDenied
        if len(choices) == 1:
            return HttpResponseRedirect(f"?ct_id={choices[0][0]}{extra_qs}")

        # When the new rich picker is enabled we still emit a simple form with
        # a hidden ct_id field that is populated by JavaScript. Otherwise we
        # fall back to the classic radio-list UI.
        use_picker = bool(self.polymorphic_type_picker)

        # Create form
        form = self.add_type_form(
            data=request.POST if request.method == "POST" else None,
            initial={"ct_id": choices[0][0]},
            use_picker=use_picker,
        )
        setattr(form.fields["ct_id"], "choices", choices)

        if form.is_valid():
            return HttpResponseRedirect(f"?ct_id={form.cleaned_data['ct_id']}{extra_qs}")

        # Wrap in all admin layout
        fieldsets = ((None, {"fields": ("ct_id",)}),)
        adminForm = AdminForm(form, fieldsets, {}, model_admin=self)  # type: ignore[arg-type]
        media = self.media + adminForm.media
        opts = self.model._meta

        context = {
            "title": _("Add %s") % force_str(opts.verbose_name),
            "adminform": adminForm,
            "is_popup": ("_popup" in request.POST or "_popup" in request.GET),
            "media": media,
            "errors": AdminErrorList(form, ()),  # type: ignore[arg-type]
            "app_label": opts.app_label,
            "polymorphic_type_picker": use_picker,
            "child_types_endpoint": self._child_types_endpoint(request),
            "favorites_endpoint": self._favorites_endpoint(request),
            "extra_query_string": extra_qs,
        }
        return self.render_add_type_form(request, context, form_url)

    def _child_types_endpoint(self, request):
        from django.urls import reverse

        app_label = self.model._meta.app_label
        model_name = self.model._meta.model_name
        return reverse(
            f"admin:{app_label}_{model_name}_child_types",
            current_app=self.admin_site.name,
        )

    def _favorites_endpoint(self, request):
        from django.urls import reverse

        app_label = self.model._meta.app_label
        model_name = self.model._meta.model_name
        return reverse(
            f"admin:{app_label}_{model_name}_favorites",
            current_app=self.admin_site.name,
        )

    def render_add_type_form(self, request, context, form_url=""):
        """
        Render the page type choice form.
        """
        opts = self.model._meta
        app_label = opts.app_label
        context.update(
            {
                "has_change_permission": self.has_change_permission(request),
                "form_url": form_url,
                "opts": opts,
                "add": True,
                "save_on_top": self.save_on_top,
                **self.admin_site.each_context(request),
            }
        )

        templates = self.add_type_template or [
            f"admin/{app_label}/{opts.object_name.lower()}/add_type_form.html",  # type: ignore[union-attr]
            f"admin/{app_label}/add_type_form.html",
            "admin/polymorphic/add_type_form.html",  # added default here
            "admin/add_type_form.html",
        ]

        request.current_app = self.admin_site.name
        return self.admin_site.admin_view(TemplateResponse)(request, templates, context)

    @property
    def change_list_template(self) -> list[str]:  # type: ignore[override]
        opts = self.model._meta
        app_label = opts.app_label

        # Pass the base options
        assert self.base_model is not None, "base_model must be set"
        base_opts = self.base_model._meta
        base_app_label = base_opts.app_label

        return [
            f"admin/{app_label}/{opts.object_name.lower()}/change_list.html",  # type: ignore[union-attr]
            f"admin/{app_label}/change_list.html",
            # Added base class:
            f"admin/{base_app_label}/{base_opts.object_name.lower()}/change_list.html",  # type: ignore[union-attr]
            f"admin/{base_app_label}/change_list.html",
            "admin/change_list.html",
        ]
