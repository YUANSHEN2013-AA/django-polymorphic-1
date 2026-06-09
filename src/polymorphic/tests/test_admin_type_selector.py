import json

from django.contrib.admin.templatetags.admin_urls import admin_urlname
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from playwright.sync_api import expect

from polymorphic.admin import PolymorphicChildModelAdmin, PolymorphicParentModelAdmin
from polymorphic.tests.admintestcase import AdminTestCase
from polymorphic.tests.models import Model2A, Model2B, Model2C, Model2D

from .utils import _GenericUITest


class PolymorphicTypeSelectorAdminTests(AdminTestCase):
    def test_add_type_view_includes_type_selector_media(self):
        @self.register(Model2A)
        class Model2Admin(PolymorphicParentModelAdmin):
            base_model = Model2A
            child_models = (Model2B, Model2C, Model2D)

        @self.register(Model2B)
        @self.register(Model2C)
        @self.register(Model2D)
        class Model2ChildAdmin(PolymorphicChildModelAdmin):
            base_model = Model2A

        response = self.admin_get_add(Model2A)
        response.render()

        assert "polymorphic/js/polymorphic_type_selector.js" in response.rendered_content
        assert "polymorphic/css/polymorphic_type_selector.css" in response.rendered_content

    def test_type_options_view_returns_categories_and_filters(self):
        @self.register(Model2A)
        class Model2Admin(PolymorphicParentModelAdmin):
            base_model = Model2A
            child_models = (Model2B, Model2C, Model2D)

        @self.register(Model2B)
        class Model2BAdmin(PolymorphicChildModelAdmin):
            base_model = Model2A
            polymorphic_type_category = "Featured"

        @self.register(Model2C)
        @self.register(Model2D)
        class Model2ChildAdmin(PolymorphicChildModelAdmin):
            base_model = Model2A

        admin_instance = self.get_admin_instance(Model2A)
        type_options_url = reverse(admin_urlname(admin_instance.opts, "type_options"))
        request = self.create_admin_request("get", f"{type_options_url}?q=Model2C")

        response = admin_instance.type_options_view(request)
        payload = json.loads(response.content)

        assert response.status_code == 200
        assert [item["object_name"] for item in payload["results"]] == ["Model2C"]

        request = self.create_admin_request("get", type_options_url)
        response = admin_instance.type_options_view(request)
        payload = json.loads(response.content)
        categories = {item["object_name"]: item["category"] for item in payload["results"]}

        assert categories["Model2B"] == "Featured"
        assert categories["Model2C"] == "Django Polymorphic"


class PolymorphicTypeSelectorUITests(_GenericUITest):
    def test_admin_type_selector_supports_search_favorites_and_recent(self):
        model2c_ct = ContentType.objects.get_for_model(Model2C)
        model2d_ct = ContentType.objects.get_for_model(Model2D)

        self.page.goto(self.admin_url())
        self.page.evaluate("window.localStorage.clear()")
        self.page.goto(self.add_url(Model2A))

        selector = self.page.locator(".polymorphic-type-selector")
        search = selector.locator("#polymorphic-type-selector-search")

        expect(selector).to_be_visible()
        expect(selector.locator(f"[data-section='categories'] [data-ct-id='{model2c_ct.pk}']")).to_have_count(1)

        search.fill("Model2C")
        expect(selector.locator(f"[data-section='categories'] [data-ct-id='{model2c_ct.pk}']")).to_have_count(1)
        expect(selector.locator(f"[data-section='categories'] [data-ct-id='{model2d_ct.pk}']")).to_have_count(0)

        search.fill("")
        favorite_button = selector.locator(
            f"[data-section='categories'] [data-ct-id='{model2d_ct.pk}'] [data-role='favorite']"
        )
        favorite_button.click()
        expect(selector.locator(f"[data-section='favorites'] [data-ct-id='{model2d_ct.pk}']")).to_have_count(1)

        selector.locator(
            f"[data-section='categories'] [data-ct-id='{model2d_ct.pk}'] [data-role='select']"
        ).click()
        with self.page.expect_navigation(timeout=30000) as nav_info:
            self.page.click("input[name='_save']")

        response = nav_info.value
        assert response.status < 400
        assert f"ct_id={model2d_ct.pk}" in self.page.url

        self.page.goto(self.add_url(Model2A))
        selector = self.page.locator(".polymorphic-type-selector")
        expect(selector).to_be_visible()
        expect(selector.locator(f"[data-section='favorites'] [data-ct-id='{model2d_ct.pk}']")).to_have_count(1)
        expect(selector.locator(f"[data-section='recent'] [data-ct-id='{model2d_ct.pk}']")).to_have_count(1)
