
from tornado.gen import coroutine, Return

import common.admin as a
import base64

from model.dlc import VersionUsesDataError
from common.environment import AppNotFound


class ApplicationController(a.AdminController):
    @coroutine
    def get(self, app_id):

        env_service = self.application.env_service

        try:
            app = yield env_service.get_app_info(self.gamespace, app_id)
        except AppNotFound as e:
            raise a.ActionError("App was not found.")

        dlc = self.application.dlc
        datas = yield dlc.list_data_versions(app_id)

        result = {
            "app_name": app["title"],
            "versions": app["versions"],
            "datas": datas
        }

        raise a.Return(result)

    @coroutine
    def new_data_version(self):

        app_id = self.context.get("app_id")

        dlc = self.application.dlc
        data_id = yield dlc.create_data_version(app_id)

        raise a.Redirect(
            "data_version",
            message="New data version has benn created",
            app_id=app_id, data_id=data_id)

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("index", "Applications")
            ], data["app_name"]),
            a.links("Application '{0}' versions".format(data["app_name"]), links=[
                a.link("app_version", v_name, icon="tags", app_id=self.context.get("app_id"),
                       version_id=v_name) for v_name, v_id in data["versions"].iteritems()
            ]),
            a.links("Data versions", [
                a.link("data_version", str(d["version_id"]), "tags",
                       app_id=self.context.get("app_id"),
                       data_id=d["version_id"])
                for d in data["datas"]
            ]),
            a.form("Actions", fields={}, methods={
                "new_data_version": a.method("New data version", "primary")
            }, data=data),
            a.links("Navigate", [
                a.link("index", "Back")
            ])
        ]

    def access_scopes(self):
        return ["dlc_admin"]


class ApplicationVersionController(a.AdminController):
    @coroutine
    def delete(self, **ignored):

        app_id = self.context.get("app_id")
        version_id = self.context.get("version_id")

        dlc = self.application.dlc

        yield dlc.delete_application_version(app_id, version_id)

        raise a.Redirect(
            "app",
            message="Application version has been detached",
            app_id=app_id)

    @coroutine
    def get(self, app_id, version_id):

        dlc = self.application.dlc
        env_service = self.application.env_service

        try:
            app = yield env_service.get_app_info(self.gamespace, app_id)
        except AppNotFound as e:
            raise a.ActionError("App was not found.")

        attach_to = yield dlc.get_application_version(app_id, version_id)

        data_versions = yield dlc.list_data_versions(app_id)

        result = {
            "app_name": app["title"],
            "attach_to": attach_to,
            "datas": data_versions
        }

        raise a.Return(result)

    def render(self, data):

        data_versions = {
            env["version_id"]: env["version_id"] for env in data["datas"]
        }

        data_versions[0] = "< NONE >"

        return [
            a.breadcrumbs([
                a.link("index", "Applications"),
                a.link("app", data["app_name"], app_id=self.context.get("app_id"))
            ], self.context.get("version_id")),
            a.form("Application version: " + self.context.get("version_id"), fields={
                "attach_to": a.field("Attach to data version", "select", "primary", "number", values=data_versions),
            }, methods={
                "update": a.method("Update", "primary", order=1),
                "delete": a.method("Detach", "danger", order=2)
            }, data=data),
            a.links("Navigate", [
                a.link("app", "Back", app_id=self.context.get("app_id")),
                a.link("new_app_version", "Add new application version", "plus", app_id=self.context.get("app_id"))
            ])
        ]

    def access_scopes(self):
        return ["dlc_admin"]

    @coroutine
    def update(self, attach_to=0):

        if attach_to == "0":
            yield self.delete()

        env_service = self.application.env_service
        app_id = self.context.get("app_id")
        version_id = self.context.get("version_id")

        try:
            yield env_service.get_app_info(self.gamespace, app_id)
        except AppNotFound as e:
            raise a.ActionError("App was not found.")

        dlc = self.application.dlc

        yield dlc.switch_app_version(app_id, version_id, attach_to)

        raise a.Redirect(
            "app_version",
            message="Application version has been updated",
            app_id=app_id, version_id=version_id)


class BundleController(a.AdminController):
    @coroutine
    def delete(self, content):

        dlc = self.application.dlc

        app_id = self.context.get("app_id")
        data_id = self.context.get("data_id")
        bundle_id = self.context.get("bundle_id")

        data_location = self.application.data_location

        yield dlc.delete_bundle(app_id, data_id, bundle_id, data_location)

        raise a.Redirect(
            "data_version",
            message="Bundle has been deleted",
            app_id=app_id, data_id=data_id)

    @coroutine
    def get(self, app_id, data_id, bundle_id):

        dlc = self.application.dlc
        env_service = self.application.env_service

        try:
            app = yield env_service.get_app_info(self.gamespace, app_id)
        except AppNotFound as e:
            raise a.ActionError("App was not found.")

        bundle = yield dlc.get_bundle(data_id, bundle_id)

        if bundle is None:
            raise a.ActionError("No such bundle")

        result = {
            "app_name": app["title"],
            "bundle_name": bundle["bundle_name"],
            "bundle_hash": bundle["bundle_hash"]
        }

        raise a.Return(result)

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("index", "Applications"),
                a.link("app", data["app_name"], app_id=self.context.get("app_id")),
                a.link("data_version", "Data #" + str(self.context.get("data_id")),
                       app_id=self.context.get("app_id"), data_id=self.context.get("data_id"))
            ], data.get("bundle_name")),
            a.form("Bundle", fields={
                "bundle_name": a.field("Bundle name", "readonly", "primary", "non-empty"),
                "bundle_hash": a.field("Bundle hash", "readonly", "primary", "non-empty"),
                "content": a.field("Upload a new content", "file", "primary"),
            }, methods={
                "update": a.method("Update", "primary"),
                "delete": a.method("Delete", "danger")
            }, data=data),
            a.links("Navigate", [
                a.link("data_version", "Back", app_id=self.context.get("app_id"), data_id=self.context.get("data_id")),
                a.link("new_bundle", "New bundle", "plus", app_id=self.context.get("app_id"),
                       data_id=self.context.get("data_id"))
            ])
        ]

    def access_scopes(self):
        return ["dlc_admin"]

    @coroutine
    def update(self, content):

        dlc = self.application.dlc
        env_service = self.application.env_service

        app_id = self.context.get("app_id")
        data_id = self.context.get("data_id")
        bundle_id = self.context.get("bundle_id")

        try:
            app = yield env_service.get_app_info(self.gamespace, app_id)
        except AppNotFound as e:
            raise a.ActionError("App was not found.")

        if not content:
            raise a.ActionError("No content passed")

        bundle = yield dlc.get_bundle(data_id, bundle_id)

        if bundle is None:
            raise a.ActionError("No such bundle")

        data_location = self.application.data_location
        host_location = self.application.data_host_location

        yield dlc.upload_bundle(app_id, data_id, bundle["bundle_name"], data_location, host_location,
                                content[0].data)

        bundle = yield dlc.get_bundle(data_id, bundle_id)

        result = {
            "app_name": app["title"],
            "bundle_name": bundle["bundle_name"],
            "bundle_hash": bundle["bundle_hash"]
        }

        raise a.Return(result)


class DataVersionController(a.AdminController):
    @coroutine
    def delete(self):

        app_id = self.context.get("app_id")
        data_id = self.context.get("data_id")

        dlc = self.application.dlc

        data_location = self.application.data_location

        try:
            yield dlc.delete_data_version(app_id, data_id, data_location)
        except VersionUsesDataError:
            raise a.ActionError("Application Version uses this data, detach the version first.")

        raise a.Redirect(
            "app",
            message="Data version has been deleted",
            app_id=app_id)

    @coroutine
    def get(self, app_id, data_id):

        dlc = self.application.dlc
        env_service = self.application.env_service

        try:
            app = yield env_service.get_app_info(self.gamespace, app_id)
        except AppNotFound as e:
            raise a.ActionError("App was not found.")

        bundles = yield dlc.list_bundles(data_id)

        result = {
            "app_name": app["title"],
            "bundles": bundles
        }

        raise a.Return(result)

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("index", "Applications"),
                a.link("app", data["app_name"], app_id=self.context.get("app_id"))
            ], "Data #" + str(self.context.get("data_id"))),
            a.links("Bundles of data version: #" + str(self.context.get("data_id")), [
                a.link("bundle", bundle["bundle_name"], "file",
                       app_id=self.context.get("app_id"),
                       data_id=self.context.get("data_id"),
                       bundle_id=bundle["bundle_id"]) for bundle in data["bundles"]
            ]),
            a.form("Actions", fields={}, methods={
                "delete": a.method("Delete data version", "danger")
            }, data=data),
            a.links("Navigate", [
                a.link("app", "Back", app_id=self.context.get("app_id")),
                a.link("new_bundle", "Add new bundle", "plus", app_id=self.context.get("app_id"),
                       data_id=self.context.get("data_id"))
            ])
        ]

    def access_scopes(self):
        return ["dlc_admin"]

class NewBundleController(a.AdminController):
    @coroutine
    def get(self, app_id, data_id):

        dlc = self.application.dlc
        env_service = self.application.env_service

        try:
            app = yield env_service.get_app_info(self.gamespace, app_id)
        except AppNotFound as e:
            raise a.ActionError("App was not found.")

        result = {
            "app_name": app["title"]
        }

        raise a.Return(result)

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("index", "Applications"),
                a.link("app", data["app_name"], app_id=self.context.get("app_id")),
                a.link("data_version", "Data #" + str(self.context.get("data_id")),
                       app_id=self.context.get("app_id"), data_id=self.context.get("data_id"))
            ], "New bundle"),
            a.form("Upload a new bundle", fields={
                "bundle_name": a.field("Bundle name", "text", "primary", "non-empty"),
                "content": a.field("Content of the new bundle", "file", "primary", "non-empty"),
            }, methods={
                "upload": a.method("Upload", "primary")
            }, data=data),
            a.links("Navigate", [
                a.link("data_version", "Back", app_id=self.context.get("app_id"), data_id=self.context.get("data_id"))
            ])
        ]

    def access_scopes(self):
        return ["dlc_admin"]

    @coroutine
    def upload(self, bundle_name, content):

        dlc = self.application.dlc

        app_id = self.context.get("app_id")
        data_id = self.context.get("data_id")

        if not content:
            raise a.ActionError("No content passed")

        data_location = self.application.data_location
        host_location = self.application.data_host_location

        yield dlc.upload_bundle(
            app_id, data_id, bundle_name, data_location, host_location, content[0].data)

        raise a.Redirect(
            "data_version",
            message="New bundle has been uploaded",
            app_id=app_id, data_id=data_id)


class RootAdminController(a.AdminController):
    @coroutine
    def get(self):

        env_service = self.application.env_service
        apps = yield env_service.list_apps(self.gamespace)

        result = {
            "apps": apps
        }

        raise a.Return(result)

    def render(self, data):
        return [
            a.breadcrumbs([], "Applications"),
            a.links("Applications", [
                a.link("app", app_name, icon="mobile", app_id=app_id)
                    for app_id, app_name in data["apps"].iteritems()
            ]),
            a.links("Navigate", [
                a.link("/environment/apps", "Edit applications", icon="mobile")
            ])
        ]

    def access_scopes(self):
        return ["dlc_admin"]
