from __future__ import annotations

import json
from typing import Any

from django import forms
from django.conf import settings
from django.contrib.admin.widgets import AdminRadioSelect
from django.forms import Media
from django.utils.translation import gettext_lazy as _


class PolymorphicModelChoiceForm(forms.Form):
    """
    The default form for the ``add_type_form``. Can be overwritten and replaced.
    """

    type_label = _("Type")

    ct_id = forms.ChoiceField(
        label=type_label, widget=AdminRadioSelect(attrs={"class": "radiolist"})
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["ct_id"].label = self.type_label


class PolymorphicTypeSelectWidget(forms.Widget):
    """
    A widget that renders an enhanced type selection interface with:
    - Search/filter
    - Favorites (localStorage)
    - Recently used (localStorage)
    - Categorized display
    - Async loading of subclass list
    """

    template_name = "admin/polymorphic/widgets/type_select.html"
    input_type = "hidden"

    class Media:
        js = (
            "polymorphic/js/polymorphic_type_select.js",
        )
        css = {
            "all": ("polymorphic/css/polymorphic_type_select.css",),
        }

    def __init__(self, attrs=None, type_data_url: str = "", choices=None):
        super().__init__(attrs)
        self.type_data_url = type_data_url
        self.choices = choices or []

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["type"] = self.input_type
        context["widget"]["type_data_url"] = self.type_data_url
        context["widget"]["initial_choices"] = json.dumps(self.choices)
        return context

    def value_from_datadict(self, data, files, name):
        return data.get(name)


class PolymorphicTypeSelectForm(forms.Form):
    """
    Enhanced form for the polymorphic add type view.
    Uses PolymorphicTypeSelectWidget for a rich type selection experience.
    """

    type_label = _("Type")

    ct_id = forms.CharField(
        label=type_label,
        widget=PolymorphicTypeSelectWidget,
    )

    def __init__(
        self, *args: Any, type_data_url: str = "", choices: list | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["ct_id"].label = self.type_label
        if type_data_url:
            self.fields["ct_id"].widget.type_data_url = type_data_url
        if choices:
            self.fields["ct_id"].widget.choices = choices