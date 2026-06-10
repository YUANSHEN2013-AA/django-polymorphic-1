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
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.template.response import TemplateResponse
from django.urls import path
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

_SESSION_FAVORITES_KEY = "polymorphic_admin_favorites"
_SESSION_RECENT_KEY = "polymorphic_admin_recent"
_MAX_RECENT_ITEMS = 10


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

    #: The regular expression to filter the primary key in the URL.
    #: This accepts only numbers as defensive measure against catch-all URLs.
    #: If your primary key consists of string values, update this regular expression.
    pk_regex = r"(\d+|__fk__)"

    #: Whether to enable the enhanced type selector with search, favorites, recent, and categories.
    enhanced_type_selector = False

    #: Group child types by app label for categorized display.
    #: Can be a callable that receives (request, child_models) and returns a dict of {group_name: [model, ...]}.
    #: Set to None to disable grouping.
    child_type_groups = None

    def __init__(self, model: type[_ModelT], admin_site: Any, *args: Any, **kwargs: Any) -> None:
        super().__init__(model, admin_site, *args, **kwargs)
        self._is_setup = False

        if self.base_model is None:
            self.base_model = get_base_polymorphic_model(model)

    def _lazy_setup(self):
        if self._is_setup:
            return

        self._child_models = self.get_child_models()

        if self._child_models and not issubclass(self._child_models[0], models.Model):
            raise ImproperlyConfigured(
                "Since django-polymorphic 1.4, the `child_models` attribute "
                "and `get_child_models()` method should be a list of models only.\n"
                "The model-admin class should be registered in the regular Django admin."
            )

        self._child_admin_site = self.admin_site
        self._is_setup = True

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
        choices = []
        content_types = ContentType.objects.get_for_models(
            *self.get_child_models(), for_concrete_models=False
        )

        for model, ct in content_types.items():
            perm_function_name = f"has_{action}_permission"
            model_admin = self._get_real_admin_by_model(model)
            perm_function = getattr(model_admin, perm_function_name)
            if not perm_function(request):
                continue
            choices.append((ct.id, model._meta.verbose_name))
        return choices

    def get_child_type_groups(self, request):
        """
        Return a dict of grouped child types for categorized display.
        By default, groups by app label.

        Override this method or set the ``child_type_groups`` attribute
        to customize grouping.

        Returns a list of dicts: [{"label": str, "models": [{"ct_id": int, "name": str, "model_name": str}]}]
        """
        self._lazy_setup()
        choices = self.get_child_type_choices(request, "add")
        content_types = ContentType.objects.get_for_models(
            *self.get_child_models(), for_concrete_models=False
        )

        if self.child_type_groups is not None:
            if callable(self.child_type_groups):
                return self.child_type_groups(request, self.get_child_models())
            return self.child_type_groups

        groups = {}
        for model, ct in content_types.items():
            if ct.id not in [c[0] for c in choices]:
                continue
            app_label = model._meta.app_label
            if app_label not in groups:
                from django.apps import apps
                app_config = apps.get_app_config(app_label)
                groups[app_label] = {
                    "label": app_config.verbose_name if app_config else app_label.title(),
                    "models": [],
                }
            groups[app_label]["models"].append({
                "ct_id": ct.id,
                "name": force_str(model._meta.verbose_name),
                "model_name": model._meta.model_name,
            })

        return list(groups.values())

    def get_child_types_data(self, request):
        """
        Return the full data structure for the enhanced type selector.
        This includes all types, groups, favorites, and recent items.
        """
        self._lazy_setup()
        choices = self.get_child_type_choices(request, "add")
        content_types = ContentType.objects.get_for_models(
            *self.get_child_models(), for_concrete_models=False
        )

        all_types = []
        for model, ct in content_types.items():
            if ct.id not in [c[0] for c in choices]:
                continue
            all_types.append({
                "ct_id": ct.id,
                "name": force_str(model._meta.verbose_name),
                "model_name": model._meta.model_name,
                "app_label": model._meta.app_label,
            })

        groups = self.get_child_type_groups(request)
        favorites = self._get_favorites(request)
        recent = self._get_recent(request)

        return {
            "all_types": all_types,
            "groups": groups,
            "favorites": [t for t in all_types if t["ct_id"] in favorites],
            "recent": [t for t in all_types if t["ct_id"] in recent],
        }

    def _get_session_key(self, suffix):
        opts = self.model._meta
        return f"{_SESSION_FAVORITES_KEY}_{opts.app_label}_{opts.model_name}_{suffix}"

    def _get_favorites(self, request):
        key = self._get_session_key("favs")
        return request.session.get(key, [])

    def _toggle_favorite(self, request, ct_id):
        key = self._get_session_key("favs")
        favorites = request.session.get(key, [])
        if ct_id in favorites:
            favorites.remove(ct_id)
        else:
            favorites.append(ct_id)
        request.session[key] = favorites
        return favorites

    def _get_recent(self, request):
        key = self._get_session_key("recent")
        return request.session.get(key, [])

    def _add_recent(self, request, ct_id):
        key = self._get_session_key("recent")
        recent = request.session.get(key, [])
        if ct_id in recent:
            recent.remove(ct_id)
        recent.insert(0, ct_id)
        recent = recent[:_MAX_RECENT_ITEMS]
        request.session[key] = recent

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
            raise Http404(e)

        model_class = ct.model_class()
        if not model_class:
            app_label, model = ct.natural_key()
            raise Http404(f"No model found for '{app_label}.{model}'.")

        return self._get_real_admin_by_model(model_class, super_if_self=super_if_self)

    def _get_real_admin_by_model(self, model_class, super_if_self=True):
        if model_class not in self._child_models:
            raise PermissionDenied(
                f"Invalid model '{model_class}', it must be registered as child model."
            )

        try:
            real_admin = self._child_admin_site._registry[model_class]
        except KeyError:
            raise ChildAdminNotRegistered(
                f"No child admin site was registered for a '{model_class}' model."
            )

        if super_if_self and real_admin is self:
            return super()
        else:
            return real_admin

    def get_queryset(self, request):
        qs = cast(PolymorphicQuerySet, super().get_queryset(request))
        if not self.polymorphic_list:
            qs = qs.non_polymorphic()
        return qs

    def add_view(self, request, form_url="", extra_context=None):
        """Redirect the add view to the real admin."""
        ct_id = int(request.GET.get("ct_id", 0))
        if not ct_id:
            return self.add_type_view(request)
        else:
            self._add_recent(request, ct_id)
            real_admin = self._get_real_admin_by_ct(ct_id)
            form_url = add_preserved_filters(
                {
                    "preserved_filters": request.GET.urlencode(),
                    "opts": self.model._meta,
                },
                form_url,
            )
            return real_admin.add_view(request, form_url, extra_context)

    def change_view(self, request, object_id, *args, **kwargs):
        """Redirect the change view to the real admin."""
        real_admin = self._get_real_admin(object_id)
        return real_admin.change_view(request, object_id, *args, **kwargs)

    def changeform_view(self, request, object_id=None, *args, **kwargs):
        if object_id:
            real_admin = self._get_real_admin(object_id)
            return real_admin.changeform_view(request, object_id, *args, **kwargs)
        else:
            return super().changeform_view(request, object_id, *args, **kwargs)

    def history_view(self, request, object_id, extra_context=None):
        """Redirect the history view to the real admin."""
        real_admin = self._get_real_admin(object_id)
        return real_admin.history_view(request, object_id, extra_context=extra_context)

    def delete_view(self, request, object_id, extra_context=None):
        """Redirect the delete view to the real admin."""
        real_admin = self._get_real_admin(object_id)
        return real_admin.delete_view(request, object_id, extra_context)

    def get_urls(self):
        """
        Expose the custom URLs for the subclasses and the URL resolver.
        """
        urls = super().get_urls()

        self._lazy_setup()

        info = self.model._meta.app_label, self.model._meta.model_name
        custom_urls = [
            path(
                "child-types-api/",
                self.admin_site.admin_view(self.child_types_api_view),
                name="%s_%s_child_types_api" % info,
            ),
            path(
                "toggle-favorite/<int:ct_id>/",
                self.admin_site.admin_view(self.toggle_favorite_api_view),
                name="%s_%s_toggle_favorite" % info,
            ),
        ]
        return custom_urls + urls

    def child_types_api_view(self, request):
        """
        API endpoint that returns child types as JSON.
        Supports async loading of the child type list.

        Query parameters:
        - search: filter types by name
        """
        if not self.has_add_permission(request):
            raise PermissionDenied

        data = self.get_child_types_data(request)

        search = request.GET.get("search", "").strip().lower()
        if search:
            data["all_types"] = [
                t for t in data["all_types"]
                if search in t["name"].lower() or search in t["model_name"].lower()
            ]
            data["groups"] = []
            for group in self.get_child_type_groups(request):
                filtered_models = [
                    m for m in group["models"]
                    if search in m["name"].lower() or search in m["model_name"].lower()
                ]
                if filtered_models:
                    data["groups"].append({
                        "label": group["label"],
                        "models": filtered_models,
                    })
            data["favorites"] = [
                t for t in data["favorites"]
                if search in t["name"].lower() or search in t["model_name"].lower()
            ]
            data["recent"] = [
                t for t in data["recent"]
                if search in t["name"].lower() or search in t["model_name"].lower()
            ]

        return JsonResponse(data)

    def toggle_favorite_api_view(self, request, ct_id):
        """
        API endpoint to toggle a child type as favorite.
        Only POST requests are allowed.
        """
        if request.method != "POST":
            return JsonResponse({"error": "Method not allowed"}, status=405)

        if not self.has_add_permission(request):
            raise PermissionDenied

        self._lazy_setup()
        choices = self.get_child_type_choices(request, "add")
        valid_ct_ids = [c[0] for c in choices]
        if ct_id not in valid_ct_ids:
            return JsonResponse({"error": "Invalid content type"}, status=400)

        favorites = self._toggle_favorite(request, ct_id)
        return JsonResponse({"favorites": favorites, "ct_id": ct_id, "is_favorite": ct_id in favorites})

    def add_type_view(self, request, form_url=""):
        """
        Display a choice form to select which page type to add.
        Supports both the enhanced type selector and the legacy radio form.
        """
        if not self.has_add_permission(request):
            raise PermissionDenied

        extra_qs = ""
        if request.META["QUERY_STRING"]:
            extra_qs = f"&{force_str(request.META['QUERY_STRING'])}"

        choices = self.get_child_type_choices(request, "add")
        if len(choices) == 0:
            raise PermissionDenied
        if len(choices) == 1:
            self._add_recent(request, choices[0][0])
            return HttpResponseRedirect(f"?ct_id={choices[0][0]}{extra_qs}")

        if self.enhanced_type_selector:
            return self._render_enhanced_type_selector(request, choices, extra_qs)

        return self._render_legacy_type_form(request, choices, extra_qs, form_url)

    def _render_enhanced_type_selector(self, request, choices, extra_qs):
        """
        Render the enhanced type selector with search, favorites, recent, and categories.
        """
        opts = self.model._meta
        api_url = f"../child-types-api/"
        toggle_favorite_url = f"../toggle-favorite/"

        types_data = self.get_child_types_data(request)

        csrf_token = ""
        if hasattr(request, 'META'):
            from django.middleware.csrf import get_token
            csrf_token = get_token(request)

        pts_options = {
            "api_url": api_url,
            "toggle_favorite_url": toggle_favorite_url,
            "extra_qs": extra_qs,
            "types_data": types_data,
            "csrf_token": csrf_token,
        }

        context = {
            "title": _("Add %s") % force_str(opts.verbose_name),
            "is_popup": ("_popup" in request.POST or "_popup" in request.GET),
            "app_label": opts.app_label,
            "opts": opts,
            "add": True,
            "has_change_permission": self.has_change_permission(request),
            "pts_options_json": json.dumps(pts_options),
            "enhanced_type_selector": True,
            **self.admin_site.each_context(request),
        }

        templates = self.add_type_template or [
            f"admin/{opts.app_label}/{opts.object_name.lower()}/add_type_form.html",
            f"admin/{opts.app_label}/add_type_form.html",
            "admin/polymorphic/add_type_form.html",
            "admin/add_type_form.html",
        ]

        request.current_app = self.admin_site.name
        return self.admin_site.admin_view(TemplateResponse)(request, templates, context)

    def _render_legacy_type_form(self, request, choices, extra_qs, form_url):
        """
        Render the legacy radio button form for backward compatibility.
        """
        form = self.add_type_form(
            data=request.POST if request.method == "POST" else None,
            initial={"ct_id": choices[0][0]},
        )
        setattr(form.fields["ct_id"], "choices", choices)

        if form.is_valid():
            ct_id = form.cleaned_data["ct_id"]
            self._add_recent(request, ct_id)
            return HttpResponseRedirect(f"?ct_id={ct_id}{extra_qs}")

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
            "enhanced_type_selector": False,
        }
        return self.render_add_type_form(request, context, form_url)

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
            "admin/polymorphic/add_type_form.html",
            "admin/add_type_form.html",
        ]

        request.current_app = self.admin_site.name
        return self.admin_site.admin_view(TemplateResponse)(request, templates, context)

    @property
    def change_list_template(self) -> list[str]:  # type: ignore[override]
        opts = self.model._meta
        app_label = opts.app_label

        assert self.base_model is not None, "base_model must be set"
        base_opts = self.base_model._meta
        base_app_label = base_opts.app_label

        return [
            f"admin/{app_label}/{opts.object_name.lower()}/change_list.html",  # type: ignore[union-attr]
            f"admin/{app_label}/change_list.html",
            f"admin/{base_app_label}/{base_opts.object_name.lower()}/change_list.html",  # type: ignore[union-attr]
            f"admin/{base_app_label}/change_list.html",
            "admin/change_list.html",
        ]

    @property
    def media(self):
        base = super().media
        if self.enhanced_type_selector:
            from django.forms import Media
            return base + Media(
                js=("polymorphic/js/polymorphic_type_selector.js",),
                css={"all": ("polymorphic/css/polymorphic_type_selector.css",)},
            )
        return base
