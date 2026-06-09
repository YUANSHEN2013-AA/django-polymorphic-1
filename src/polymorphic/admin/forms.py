from typing import Any

from django import forms
from django.contrib.admin.widgets import AdminRadioSelect
from django.utils.translation import gettext_lazy as _


class PolymorphicModelChoiceForm(forms.Form):
    """
    The default form for the ``add_type_form``. Can be overwritten and replaced.
    """

    #: Define the label for the radiofield
    type_label = _("Type")

    ct_id = forms.ChoiceField(
        label=type_label, widget=AdminRadioSelect(attrs={"class": "radiolist"})
    )

    def __init__(self, *args: Any, use_picker: bool = False, **kwargs: Any) -> None:
        # Allow to easily redefine the label (a commonly expected usecase)
        super().__init__(*args, **kwargs)
        self.fields["ct_id"].label = self.type_label
        if use_picker:
            # When the rich picker is used, JavaScript is responsible for
            # setting the value of ``ct_id`` before submitting the form.
            self.fields["ct_id"].widget = forms.HiddenInput()
