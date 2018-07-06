
from tornado.gen import coroutine, Return, Future, IOLoop
from tornado.queues import Queue

import common.admin as a
import base64
import logging
import ujson
from common import random_string

from model.data import VersionUsesDataError, DataError, NoSuchDataError, DatasModel
from model.apps import ApplicationVersionError, NoSuchApplicationVersionError, \
    NoSuchApplicationError, ApplicationError, ApplicationsModel
from model.bundle import BundleError, NoSuchBundleError, BundlesModel, BundleQueryError
from model.deploy import DeploymentMethods, DeploymentModel

from common.environment import EnvironmentClient, AppNotFound


class ApplicationController(a.AdminController):
    @coroutine
    def get(self, app_id):

        environment_client = EnvironmentClient(self.application.cache)

        try:
            app = yield environment_client.get_app_info(app_id)
        except AppNotFound as e:
            raise a.ActionError("App was not found.")

        datas = self.application.datas
        datas = yield datas.list_data_versions(self.gamespace, app_id)

        result = {
            "app_name": app.title,
            "versions": app.versions,
            "datas": datas
        }

        raise a.Return(result)

    @coroutine
    def new_data_version(self):

        app_id = self.context.get("app_id")

        datas = self.application.datas

        try:
            data_id = yield datas.create_data_version(self.gamespace, app_id)
        except DataError as e:
            raise a.ActionError(e.message)

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
                a.link("data_version", str(d.data_id), "folder",
                       app_id=self.context.get("app_id"),
                       data_id=d.data_id)
                for d in data["datas"]
            ]),
            a.form("Actions", fields={}, methods={
                "new_data_version": a.method("New data version", "primary")
            }, data=data),
            a.links("Navigate", [
                a.link("index", "Back", icon="chevron-left"),
                a.link("app_settings", "Application Settings", icon="cog", app_id=self.context.get("app_id"))
            ])
        ]

    def access_scopes(self):
        return ["dlc_admin"]


class ApplicationVersionController(a.AdminController):
    @coroutine
    def delete(self, **ignored):

        app_id = self.context.get("app_id")
        version_id = self.context.get("version_id")

        app_versions = self.application.app_versions

        try:
            yield app_versions.delete_application_version(self.gamespace, app_id, version_id)
        except ApplicationVersionError as e:
            raise a.ActionError(e.message)

        raise a.Redirect(
            "app",
            message="Application version has been detached",
            app_id=app_id)

    @coroutine
    def get(self, app_id, version_id):

        app_versions = self.application.app_versions
        datas = self.application.datas
        environment_client = EnvironmentClient(self.application.cache)

        try:
            app = yield environment_client.get_app_info(app_id)
        except AppNotFound as e:
            raise a.ActionError("App was not found.")

        try:
            v = yield app_versions.get_application_version(app_id, version_id)
        except NoSuchApplicationVersionError:
            attach_to = 0
        except ApplicationVersionError as e:
            raise a.ActionError(e.message)
        else:
            attach_to = v.current

        try:
            data_versions = yield datas.list_data_versions(self.gamespace, app_id, published=True)
        except DataError as e:
            raise a.ActionError(e.message)

        result = {
            "app_name": app.title,
            "attach_to": attach_to,
            "datas": data_versions
        }

        raise a.Return(result)

    def render(self, data):

        data_versions = {
            env.data_id: env.data_id for env in data["datas"]
        }

        data_versions[0] = "< NONE >"

        return [
            a.breadcrumbs([
                a.link("index", "Applications"),
                a.link("app", data["app_name"], app_id=self.context.get("app_id"))
            ], self.context.get("version_id")),
            a.form("Application version: " + self.context.get("version_id"), fields={
                "attach_to": a.field("Attach to data version (should be published)",
                                     "select", "primary", "number", values=data_versions),
            }, methods={
                "update": a.method("Update", "primary", order=1),
                "delete": a.method("Detach", "danger", order=2)
            }, data=data),
            a.links("Navigate", [
                a.link("app", "Back", app_id=self.context.get("app_id"))
            ])
        ]

    def access_scopes(self):
        return ["dlc_admin"]

    @coroutine
    def update(self, attach_to=0):

        if attach_to == "0":
            yield self.delete()

        environment_client = EnvironmentClient(self.application.cache)
        app_id = self.context.get("app_id")
        version_id = self.context.get("version_id")

        try:
            yield environment_client.get_app_info(app_id)
        except AppNotFound as e:
            raise a.ActionError("App was not found.")

        app_versions = self.application.app_versions

        try:
            yield app_versions.switch_app_version(self.gamespace, app_id, version_id, attach_to)
        except ApplicationVersionError as e:
            raise a.ActionError(e.message)

        raise a.Redirect(
            "app_version",
            message="Application version has been updated",
            app_id=app_id, version_id=version_id)


class BundleController(a.UploadAdminController):
    def __init__(self, app, token):
        super(BundleController, self).__init__(app, token)

        self.chunks = Queue(10)

    @coroutine
    def detach(self, **ignored):

        bundles = self.application.bundles
        datas = self.application.datas

        app_id = self.context.get("app_id")
        bundle_id = self.context.get("bundle_id")
        data_id = self.context.get("data_id")

        try:
            bundle = yield bundles.get_bundle(self.gamespace, bundle_id)
        except NoSuchBundleError:
            raise a.ActionError("No such bundle error")
        except BundleError as e:
            raise a.ActionError(e.message)

        try:
            yield datas.get_data_version(self.gamespace, data_id)
        except NoSuchDataError:
            raise a.ActionError("No such data version")
        except DataError as e:
            raise a.ActionError(e.message)

        try:
            yield bundles.detach_bundle(self.gamespace, bundle_id, data_id)
        except NoSuchBundleError:
            raise a.ActionError("No such bundle error")
        except BundleError as e:
            raise a.ActionError(e.message)

        raise a.Redirect(
            "data_version",
            message="Bundle has been detached",
            app_id=app_id,
            data_id=data_id)

    @coroutine
    def delete(self, **ignored):

        datas = self.application.datas
        bundles = self.application.bundles

        app_id = self.context.get("app_id")
        bundle_id = self.context.get("bundle_id")
        data_id = self.context.get("data_id")

        try:
            bundle = yield bundles.get_bundle(self.gamespace, bundle_id)
        except NoSuchBundleError:
            raise a.ActionError("No such bundle error")
        except BundleError as e:
            raise a.ActionError(e.message)

        try:
            yield datas.get_data_version(self.gamespace, data_id)
        except NoSuchDataError:
            raise a.ActionError("No such data version")
        except DataError as e:
            raise a.ActionError(e.message)

        try:
            yield bundles.delete_bundle(self.gamespace, app_id, bundle_id)
        except NoSuchBundleError:
            raise a.ActionError("No such bundle error")
        except BundleError as e:
            raise a.ActionError(e.message)

        raise a.Redirect(
            "data_version",
            message="Bundle has been deleted",
            app_id=app_id,
            data_id=data_id)

    @staticmethod
    def sizeof_fmt(num, suffix='B'):
        for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
            if abs(num) < 1024.0:
                return "%3.1f%s%s" % (num, unit, suffix)
            num /= 1024.0
        return "%.1f%s%s" % (num, 'Yi', suffix)

    @coroutine
    def update_properties(self, bundle_filters, bundle_payload):

        datas = self.application.datas
        bundles = self.application.bundles
        environment_client = EnvironmentClient(self.application.cache)

        app_id = self.context.get("app_id")
        bundle_id = self.context.get("bundle_id")
        data_id = self.context.get("data_id")

        try:
            bundle_filters = ujson.loads(bundle_filters)
        except (KeyError, ValueError):
            raise a.ActionError("Corrupted filters")

        try:
            bundle_payload = ujson.loads(bundle_payload)
        except (KeyError, ValueError):
            raise a.ActionError("Corrupted payload")

        try:
            app = yield environment_client.get_app_info(app_id)
        except AppNotFound as e:
            raise a.ActionError("App was not found.")

        try:
            bundle = yield bundles.get_bundle(self.gamespace, bundle_id)
        except NoSuchBundleError:
            raise a.ActionError("No such bundle")
        except BundleError as e:
            raise a.ActionError(e.message)

        try:
            yield datas.get_data_version(self.gamespace, data_id)
        except NoSuchDataError:
            raise a.ActionError("No such data version")
        except DataError as e:
            raise a.ActionError(e.message)

        try:
            yield bundles.update_bundle_properties(self.gamespace, bundle_id, bundle_filters, bundle_payload)
        except NoSuchBundleError:
            raise a.ActionError("No such bundle")
        except BundleError as e:
            raise a.ActionError(e.message)

        raise a.Redirect("bundle",
                         message="Bundle filters has been updated",
                         app_id=app_id,
                         bundle_id=bundle_id,
                         data_id=data_id)

    @coroutine
    def get(self, app_id, bundle_id, data_id):

        bundles = self.application.bundles
        datas = self.application.datas
        environment_client = EnvironmentClient(self.application.cache)
        apps = self.application.app_versions

        try:
            app = yield environment_client.get_app_info(app_id)
        except AppNotFound as e:
            raise a.ActionError("App was not found.")

        try:
            stt = yield apps.get_application(self.gamespace, app_id)
        except NoSuchApplicationError:
            filters_scheme = ApplicationsModel.DEFAULT_FILTERS_SCHEME
            payload_scheme = ApplicationsModel.DEFAULT_PAYLOAD_SCHEME
        except ApplicationError as e:
            raise a.ActionError(e.message)
        else:
            filters_scheme = stt.filters_scheme
            payload_scheme = stt.payload_scheme

        try:
            data = yield datas.get_data_version(self.gamespace, data_id)
        except NoSuchDataError:
            raise a.ActionError("No such data version")
        except DataError as e:
            raise a.ActionError(e.message)

        try:
            bundle = yield bundles.get_bundle(self.gamespace, bundle_id, data_id)
        except NoSuchBundleError:
            raise a.ActionError("No such bundle")
        except BundleError as e:
            raise a.ActionError(e.message)

        result = {
            "app_name": app.title,
            "bundle_name": bundle.name,
            "bundle_status": bundle.status,
            "data_status": data.status,
            "bundle_size": BundleController.sizeof_fmt(bundle.size),
            "bundle_hash": bundle.hash if bundle.hash else "(Not uploaded yet)",
            "bundle_filters": bundle.filters,
            "bundle_payload": bundle.payload,
            "bundle_url": bundle.url if bundle.url else "(Not deployed yet)",
            "filters_scheme": filters_scheme,
            "payload_scheme": payload_scheme
        }

        raise a.Return(result)

    def render(self, data):

        data_id = self.context.get("data_id")

        r = [
            a.breadcrumbs([
                a.link("index", "Applications"),
                a.link("app", data["app_name"], app_id=self.context.get("app_id")),
                a.link("data_version", "Data #" + str(data_id),
                       app_id=self.context.get("app_id"), data_id=data_id)
            ], data.get("bundle_name"))
        ]

        if data["bundle_status"] == BundlesModel.STATUS_DELIVERED:
            r.append(a.notice(
                "Bundle has been delivered",
                """
                    This bundle has been successfully delivered.
                    Therefore it cannot be edited anymore.
                    However, if the data not yet published, the bundle can be detached for the data.
                """))
        else:
            r.append(a.file_upload("Upload contents"))

        r.extend([
            a.form("Bundle", fields={
                "bundle_status": a.field("Status", "status", {
                    BundlesModel.STATUS_CREATED: "default",
                    BundlesModel.STATUS_UPLOADED: "info",
                    BundlesModel.STATUS_DELIVERED: "success",
                    BundlesModel.STATUS_ERROR: "danger",
                    BundlesModel.STATUS_DELIVERING: "info",
                }.get(data["bundle_status"], "Unknown"), icon={
                    BundlesModel.STATUS_CREATED: "cog fa-spin",
                    BundlesModel.STATUS_UPLOADED: "check",
                    BundlesModel.STATUS_DELIVERED: "check",
                    BundlesModel.STATUS_ERROR: "exclamation-triangle",
                    BundlesModel.STATUS_DELIVERING: "refresh fa-spin",
                }.get(data["bundle_status"], ""), order=1),
                "bundle_name": a.field("Bundle name", "readonly", "primary", "non-empty", order=2),
                "bundle_size": a.field("Bundle size", "readonly", "primary", "non-empty", order=3),
                "bundle_hash": a.field("Bundle hash", "readonly", "primary", "non-empty", order=4),
                "bundle_url": a.field("Bundle URL", "readonly", "primary", "non-empty", order=5)
            }, methods={
                "delete": a.method("Delete", "danger")
            } if (data["bundle_status"] != BundlesModel.STATUS_DELIVERED) else {}, data=data),

            a.form("Bundle properties", fields={
                "bundle_payload": a.field(
                    "Bundle payload", "dorn", "primary", schema=data["payload_scheme"], order=1),
                "bundle_filters": a.field(
                    "Bundle filters", "dorn", "primary", schema=data["filters_scheme"], order=2)
            }, methods={
                "update_properties": a.method("Update", "primary")
            }, data=data)])

        if data["data_status"] != DatasModel.STATUS_PUBLISHED:
            r.append(a.form("Detach bundle from this data", fields={}, methods={
                "detach": a.method(
                    "Detach", "danger",
                    danger="Warning: This operation is destructive. If you lost the bundle's hash, this bundle can be "
                           "no longer attached."),
            }, data=data))

        r.extend([
            a.links("Navigate", [
                a.link("data_version", "Back", app_id=self.context.get("app_id"), data_id=data_id),
                a.link("new_bundle", "New bundle", "plus", app_id=self.context.get("app_id"),
                       data_id=data_id)
            ])
        ])

        return r

    def access_scopes(self):
        return ["dlc_admin"]

    @coroutine
    def receive_started(self, filename, args):

        bundles = self.application.bundles
        environment_client = EnvironmentClient(self.application.cache)

        app_id = self.context.get("app_id")
        bundle_id = self.context.get("bundle_id")

        try:
            app = yield environment_client.get_app_info(app_id)
        except AppNotFound as e:
            raise a.ActionError("App was not found.")

        try:
            bundle = yield bundles.get_bundle(self.gamespace, bundle_id)
        except NoSuchBundleError:
            raise a.ActionError("No such bundle")
        except BundleError as e:
            raise a.ActionError(e.message)

        IOLoop.current().add_callback(
            bundles.upload_bundle,
            self.gamespace, app_id, bundle,
            self.__producer__)

    @coroutine
    def receive_data(self, chunk):
        yield self.chunks.put(chunk)

    @coroutine
    def receive_completed(self):

        yield self.chunks.put(None)

        app_id = self.context.get("app_id")
        bundle_id = self.context.get("bundle_id")
        data_id = self.context.get("data_id")

        raise a.Redirect("bundle",
                         message="Bundle has been uploaded",
                         app_id=app_id,
                         bundle_id=bundle_id,
                         data_id=data_id)

    @coroutine
    def __producer__(self, write):
        while True:
            chunk = yield self.chunks.get()
            if chunk is None:
                return
            yield write(chunk)


class DataVersionController(a.AdminController):
    @coroutine
    def delete(self):

        app_id = self.context.get("app_id")
        data_id = self.context.get("data_id")

        datas = self.application.datas

        try:
            yield datas.delete_data_version(self.gamespace, app_id, data_id)
        except VersionUsesDataError:
            raise a.ActionError("Application Version uses this data, detach the version first.")

        raise a.Redirect(
            "app",
            message="Data version has been deleted",
            app_id=app_id)

    @coroutine
    def publish(self, **ignored):

        datas = self.application.datas
        environment_client = EnvironmentClient(self.application.cache)

        app_id = self.context.get("app_id")
        data_id = self.context.get("data_id")

        try:
            app = yield environment_client.get_app_info(app_id)
        except AppNotFound as e:
            raise a.ActionError("App was not found.")

        try:
            yield datas.publish(self.gamespace, data_id)
        except NoSuchDataError:
            raise a.ActionError("No such data version")
        except DataError as e:
            raise a.ActionError(e.message)

        raise a.Redirect("data_version",
                         message="Publish process has been started",
                         app_id=app_id, data_id=data_id)

    @coroutine
    def get(self, app_id, data_id):

        bundles = self.application.bundles
        datas = self.application.datas
        environment_client = EnvironmentClient(self.application.cache)

        try:
            app = yield environment_client.get_app_info(app_id)
        except AppNotFound as e:
            raise a.ActionError("App was not found.")

        try:
            data = yield datas.get_data_version(self.gamespace, data_id)
        except NoSuchDataError:
            raise a.ActionError("No such data version")
        except DataError as e:
            raise a.ActionError(e.message)

        try:
            bundles = yield bundles.list_bundles(self.gamespace, data_id)
        except BundleError as e:
            raise a.ActionError(e.message)

        result = {
            "app_name": app.title,
            "bundles": bundles,
            "data_status": data.status + (": " + str(data.reason) if data.reason else "")
        }

        raise a.Return(result)

    def render(self, data):

        r = [
            a.breadcrumbs([
                a.link("index", "Applications"),
                a.link("app", data["app_name"], app_id=self.context.get("app_id"))
            ], "Data #" + str(self.context.get("data_id"))),

            a.content("Bundles of data version: #" + str(self.context.get("data_id")), headers=[
                {
                    "id": "name",
                    "title": "Bundle"
                },
                {
                    "id": "filters",
                    "title": "Bundle filters"
                },
                {
                    "id": "size",
                    "title": "Bundle size"
                },
                {
                    "id": "download",
                    "title": "Download"
                },
                {
                    "id": "hash",
                    "title": "Bundle hash (last 24 chars)"
                },
                {
                    "id": "status",
                    "title": "Status"
                }
            ], items=[
                {
                    "name": [
                        a.link("bundle", bundle.name, "file",
                               app_id=self.context.get("app_id"),
                               bundle_id=bundle.bundle_id,
                               data_id=self.context.get("data_id"))
                    ],
                    "size": BundleController.sizeof_fmt(bundle.size) if bundle.size else [
                        a.status("Empty", "info")
                    ],
                    "filters": [
                        a.json_view(bundle.filters)
                    ],
                    "hash": bundle.hash[-24:] if bundle.hash else [
                        a.status("No hash", "info")
                    ],
                    "download": [
                        a.link(bundle.url, "Download", icon="download")
                    ] if bundle.url else [
                        a.status("Not deployed yet", "info")
                    ],
                    "status": [
                        a.status(bundle.status, style={
                            BundlesModel.STATUS_CREATED: "default",
                            BundlesModel.STATUS_UPLOADED: "info",
                            BundlesModel.STATUS_DELIVERED: "success",
                            BundlesModel.STATUS_ERROR: "danger",
                            BundlesModel.STATUS_DELIVERING: "info"
                        }.get(bundle.status, "danger"), icon={
                            BundlesModel.STATUS_CREATED: "cog fa-spin",
                            BundlesModel.STATUS_UPLOADED: "check",
                            BundlesModel.STATUS_DELIVERED: "check",
                            BundlesModel.STATUS_ERROR: "exclamation-triangle",
                            BundlesModel.STATUS_DELIVERING: "refresh fa-spin"
                        }.get(bundle.status, ""))
                    ]
                }
                for bundle in data["bundles"]
            ], style="primary", empty="No bundles in this data")
        ]

        status = data["data_status"]

        if status == DatasModel.STATUS_PUBLISHED:
            r.extend([
                a.form("Actions", fields={
                    "data_status": a.field("Status", "status", "success")
                }, methods={}, data=data),
                a.links("Navigate", [
                    a.link("app", "Back", app_id=self.context.get("app_id"))
                ])
            ])
        else:
            r.extend([
                a.notice(
                    "In order to be delivered, the data version should be published",
                     """
                        Once published, no bundles can be changed or deleted.
                        To publish this data version, please press the button below.
                     """),
                a.form("Actions", fields={
                    "data_status": a.field("Status", "status", {
                        DatasModel.STATUS_CREATED: "default",
                        DatasModel.STATUS_PUBLISHED: "success",
                        DatasModel.STATUS_PUBLISHING: "info"
                    }.get(data["data_status"], "danger"), icon={
                        DatasModel.STATUS_CREATED: "cog fa-spin",
                        DatasModel.STATUS_PUBLISHED: "check",
                        DatasModel.STATUS_PUBLISHING: "refresh fa-spin"
                    }.get(data["data_status"], "error"))
                }, methods={
                    "delete": a.method("Delete", "danger", order=1),
                    "publish": a.method("Publish this data version", "success", order=2)
                }, data=data),
                a.links("Navigate", [
                    a.link("app", "Back", app_id=self.context.get("app_id")),
                    a.link("new_bundle", "Add new bundle", "plus", app_id=self.context.get("app_id"),
                           data_id=self.context.get("data_id")),
                    a.link("attach_bundle", "Attach existing bundle", "plus-circle",
                           app_id=self.context.get("app_id"),
                           data_id=self.context.get("data_id"))
                ])
            ])

        return r

    def access_scopes(self):
        return ["dlc_admin"]


class NewBundleController(a.AdminController):
    @coroutine
    def get(self, app_id, data_id):

        datas = self.application.datas
        apps = self.application.app_versions
        environment_client = EnvironmentClient(self.application.cache)

        try:
            app = yield environment_client.get_app_info(app_id)
        except AppNotFound as e:
            raise a.ActionError("App was not found.")

        try:
            stt = yield apps.get_application(self.gamespace, app_id)
        except NoSuchApplicationError:
            filters_scheme = ApplicationsModel.DEFAULT_FILTERS_SCHEME
            payload_scheme = ApplicationsModel.DEFAULT_PAYLOAD_SCHEME
        except ApplicationError as e:
            raise a.ActionError(e.message)
        else:
            filters_scheme = stt.filters_scheme
            payload_scheme = stt.payload_scheme

        try:
            yield datas.get_data_version(self.gamespace, data_id)
        except DataError as e:
            raise a.ActionError(e.message)
        except NoSuchDataError:
            raise a.ActionError("No such data")

        result = {
            "app_name": app.title,
            "filters_scheme": filters_scheme,
            "payload_scheme": payload_scheme
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
            a.form("Create a new bundle", fields={
                "bundle_name": a.field("Bundle name", "text", "primary", "non-empty", order=1),
                "bundle_payload": a.field("Bundle payload", "dorn", "primary", schema=data["payload_scheme"], order=2),
                "bundle_filters": a.field("Bundle filters", "dorn", "primary", schema=data["filters_scheme"], order=3)
            }, methods={
                "create": a.method("Create", "primary")
            }, data=data),
            a.links("Navigate", [
                a.link("data_version", "Back", app_id=self.context.get("app_id"), data_id=self.context.get("data_id"))
            ])
        ]

    def access_scopes(self):
        return ["dlc_admin"]

    @coroutine
    def create(self, bundle_name, bundle_filters, bundle_payload, **ignored):

        bundles = self.application.bundles

        try:
            bundle_filters = ujson.loads(bundle_filters)
        except (KeyError, ValueError):
            raise a.ActionError("Corrupted bundle filters")

        try:
            bundle_payload = ujson.loads(bundle_payload)
        except (KeyError, ValueError):
            raise a.ActionError("Corrupted bundle payload")

        app_id = self.context.get("app_id")
        data_id = self.context.get("data_id")

        bundle_key = random_string(32)

        try:
            bundle_id = yield bundles.create_bundle(
                self.gamespace, data_id, bundle_name,
                bundle_filters, bundle_payload, bundle_key)
        except BundleError as e:
            raise a.ActionError(e.message)

        raise a.Redirect(
            "bundle",
            message="New bundle has been created",
            app_id=app_id,
            bundle_id=bundle_id,
            data_id=data_id)


class RootAdminController(a.AdminController):
    @coroutine
    def get(self):

        environment_client = EnvironmentClient(self.application.cache)
        apps = yield environment_client.list_apps()

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


class ApplicationSettingsController(a.AdminController):
    @coroutine
    def get(self, app_id):

        environment_client = EnvironmentClient(self.application.cache)
        apps = self.application.app_versions

        try:
            app = yield environment_client.get_app_info(app_id)
        except AppNotFound as e:
            raise a.ActionError("App was not found.")

        try:
            settings = yield apps.get_application(self.gamespace, app_id)
        except NoSuchApplicationError:
            deployment_method = ""
            deployment_data = {}
            payload_scheme = ApplicationsModel.DEFAULT_PAYLOAD_SCHEME
            filters_scheme = ApplicationsModel.DEFAULT_FILTERS_SCHEME
        except ApplicationError as e:
            raise a.ActionError(e.message)
        else:
            deployment_method = settings.deployment_method
            deployment_data = settings.deployment_data
            filters_scheme = settings.filters_scheme
            payload_scheme = settings.payload_scheme

        deployment_methods = { t: t for t in DeploymentMethods.types() }

        if not deployment_method:
            deployment_methods[""] = "< SELECT >"

        result = {
            "app_name": app.title,
            "deployment_methods": deployment_methods,
            "deployment_method": deployment_method,
            "deployment_data": deployment_data,
            "filters_scheme": filters_scheme,
            "payload_scheme": payload_scheme
        }

        raise a.Return(result)

    @coroutine
    def update_deployment_method(self, deployment_method):

        app_id = self.context.get("app_id")

        environment_client = EnvironmentClient(self.application.cache)
        apps = self.application.app_versions

        try:
            yield environment_client.get_app_info(app_id)
        except AppNotFound as e:
            raise a.ActionError("App was not found.")

        if not DeploymentMethods.valid(deployment_method):
            raise a.ActionError("Not a valid deployment method")

        try:
            stt = yield apps.get_application(self.gamespace, app_id)
        except NoSuchApplicationError:
            deployment_data = {}
            filters_scheme = ApplicationsModel.DEFAULT_FILTERS_SCHEME
            payload_scheme = ApplicationsModel.DEFAULT_PAYLOAD_SCHEME
        else:
            deployment_data = stt.deployment_data
            filters_scheme = stt.filters_scheme
            payload_scheme = stt.payload_scheme

        try:
            yield apps.update_application(
                self.gamespace, app_id, deployment_method,
                deployment_data, filters_scheme, payload_scheme)
        except ApplicationError as e:
            raise a.ActionError(e.message)

        raise a.Redirect("app_settings", message="Deployment method has been updated",
                         app_id=app_id)

    @coroutine
    def update_deployment(self, **kwargs):

        app_id = self.context.get("app_id")

        environment_client = EnvironmentClient(self.application.cache)
        apps = self.application.app_versions

        try:
            app = yield environment_client.get_app_info(app_id)
        except AppNotFound as e:
            raise a.ActionError("App was not found.")

        try:
            settings = yield apps.get_application(self.gamespace, app_id)
        except NoSuchApplicationError:
            raise a.ActionError("Please select deployment method first")
        except ApplicationError as e:
            raise a.ActionError(e.message)
        else:
            deployment_method = settings.deployment_method
            deployment_data = settings.deployment_data
            filters_scheme = settings.filters_scheme
            payload_scheme = settings.payload_scheme

        m = DeploymentMethods.get(deployment_method)()

        m.load(deployment_data)
        yield m.update(**kwargs)

        try:
            yield apps.update_application(
                self.gamespace, app_id, deployment_method,
                m.dump(), filters_scheme, payload_scheme)
        except ApplicationError as e:
            raise a.ActionError(e.message)

        raise a.Redirect("app_settings", message="Deployment settings have been updated",
                         app_id=app_id)

    @coroutine
    def update_scheme(self, filters_scheme, payload_scheme):

        app_id = self.context.get("app_id")

        environment_client = EnvironmentClient(self.application.cache)
        apps = self.application.app_versions

        try:
            filters_scheme = ujson.loads(filters_scheme)
        except (KeyError, ValueError):
            raise a.ActionError("Corrupted filters scheme")

        try:
            payload_scheme = ujson.loads(payload_scheme)
        except (KeyError, ValueError):
            raise a.ActionError("Corrupted payload scheme")

        try:
            app = yield environment_client.get_app_info(app_id)
        except AppNotFound as e:
            raise a.ActionError("App was not found.")

        try:
            settings = yield apps.get_application(self.gamespace, app_id)
        except NoSuchApplicationError:
            raise a.ActionError("Please select deployment method first")
        except ApplicationError as e:
            raise a.ActionError(e.message)
        else:
            deployment_method = settings.deployment_method
            deployment_data = settings.deployment_data

        try:
            yield apps.update_application(
                self.gamespace, app_id, deployment_method,
                deployment_data, filters_scheme, payload_scheme)
        except ApplicationError as e:
            raise a.ActionError(e.message)

        raise a.Redirect("app_settings", message="Deployment settings have been updated",
                         app_id=app_id)

    def render(self, data):

        r = [
            a.breadcrumbs([
                a.link("index", "Applications"),
                a.link("app", data["app_name"], app_id=self.context.get("app_id"))
            ], "Settings"),
            a.form("Deployment method", fields={
                "deployment_method": a.field(
                    "Deployment method", "select", "primary", "non-empty", values=data["deployment_methods"]
                )
            }, methods={
                "update_deployment_method": a.method("Switch deployment method", "primary")
            }, data=data)
        ]

        deployment_method = data["deployment_method"]
        deployment_data = data["deployment_data"]

        if deployment_method:
            m = DeploymentMethods.get(deployment_method)
            if m.has_admin():
                r.append(a.form("Update deployment", fields=m.render(a), methods={
                    "update_deployment": a.method("Update", "primary")
                }, data=deployment_data))

            r.append(a.form("Update schemes", fields={
                "payload_scheme": a.field("""
                    This scheme is used to define custom attributes for each bundle.
                """, "json", "primary", "non-empty", height="500", order=1),
                "filters_scheme": a.field("""
                    This scheme is used to define list of possible filters for each bundle for this application.
                """, "json", "primary", "non-empty", height="500", order=2)
            }, methods={
                "update_scheme": a.method("Update", "primary")
            }, data=data))
        else:
            r.append(a.notice(
                "Please select deployment method",
                """
                    To edit filters scheme, please select the deployment method above
                """))

        r.extend([
            a.links("Navigate", [
                a.link("app", "Back", app_id=self.context.get("app_id")),
            ])
        ])

        return r

    def access_scopes(self):
        return ["dlc_admin"]


class AttachBundleController(a.AdminController):
    @coroutine
    def get(self, app_id, data_id):

        datas = self.application.datas
        environment_client = EnvironmentClient(self.application.cache)

        try:
            app = yield environment_client.get_app_info(app_id)
        except AppNotFound as e:
            raise a.ActionError("App was not found.")

        try:
            yield datas.get_data_version(self.gamespace, data_id)
        except DataError as e:
            raise a.ActionError(e.message)
        except NoSuchDataError:
            raise a.ActionError("No such data")

        result = {
            "app_name": app.title
        }

        raise a.Return(result)

    def render(self, data):
        return [
            a.breadcrumbs([
                a.link("index", "Applications"),
                a.link("app", data["app_name"], app_id=self.context.get("app_id")),
                a.link("data_version", "Data #" + str(self.context.get("data_id")),
                       app_id=self.context.get("app_id"), data_id=self.context.get("data_id"))
            ], "Attach bundle"),
            a.notice("About attaching",
                     """
                        This page allows to attach existing bundle into a new data, reusing disk space.
                        Please note, the bundle should be delivered in order to do that.
                     """),
            a.form("Attach existing bundle", fields={
                "bundle_name": a.field("Bundle name", "text", "primary", "non-empty", order=1),
                "bundle_hash": a.field("Bundle hash", "text", "primary", "non-empty", order=2)
            }, methods={
                "attach": a.method("Attach", "primary")
            }, data=data),
            a.links("Navigate", [
                a.link("data_version", "Back", app_id=self.context.get("app_id"), data_id=self.context.get("data_id"))
            ])
        ]

    def access_scopes(self):
        return ["dlc_admin"]

    @coroutine
    def attach(self, bundle_name, bundle_hash):

        datas = self.application.datas
        bundles = self.application.bundles
        environment_client = EnvironmentClient(self.application.cache)

        app_id = self.context.get("app_id")
        data_id = self.context.get("data_id")

        try:
            app = yield environment_client.get_app_info(app_id)
        except AppNotFound as e:
            raise a.ActionError("App was not found.")

        try:
            yield datas.get_data_version(self.gamespace, data_id)
        except DataError as e:
            raise a.ActionError(e.message)
        except NoSuchDataError:
            raise a.ActionError("No such data")

        q = bundles.bundles_query(self.gamespace)

        q.name = bundle_name
        q.hash = bundle_hash
        q.status = BundlesModel.STATUS_DELIVERED

        try:
            bundle = yield q.query(one=True)
        except BundleQueryError as e:
            raise a.ActionError(e.message)

        if not bundle:
            raise a.ActionError("No such bundle")

        try:
            yield bundles.attach_bundle(
                self.gamespace, bundle.bundle_id, data_id)
        except BundleError as e:
            raise a.ActionError(e.message)

        raise a.Redirect(
            "bundle",
            message="Bundle has been attached",
            app_id=app_id,
            bundle_id=bundle.bundle_id,
            data_id=data_id)
