
from anthill.common.options import options
from anthill.common import server, handler, keyvalue, database, access

from . model.deploy import DeploymentModel
from . model.bundle import BundlesModel
from . model.data import DatasModel
from . model.apps import ApplicationsModel

from . import handler
from . import admin
from . import options as _opts


class DLCServer(server.Server):
    def __init__(self):
        super(DLCServer, self).__init__()

        self.db = database.Database(
            host=options.db_host,
            database=options.db_name,
            user=options.db_username,
            password=options.db_password)

        self.cache = keyvalue.KeyValueStorage(
            host=options.cache_host,
            port=options.cache_port,
            db=options.cache_db,
            max_connections=options.cache_max_connections)

        self.data_host_location = options.data_host_location

        self.app_versions = ApplicationsModel(self.db)
        self.bundles = BundlesModel(self.db)
        self.deployment = DeploymentModel(self.bundles, self.app_versions)
        self.datas = DatasModel(self.bundles, self.deployment, self.db)

    def get_models(self):
        return [self.datas, self.bundles, self.deployment, self.app_versions]

    def get_admin(self):
        return {
            "index": admin.RootAdminController,
            "app": admin.ApplicationController,
            "app_version": admin.ApplicationVersionController,
            "data_version": admin.DataVersionController,
            "bundle": admin.BundleController,
            "new_bundle": admin.NewBundleController,
            "attach_bundle": admin.AttachBundleController,
            "app_settings": admin.ApplicationSettingsController
        }

    def get_metadata(self):
        return {
            "title": "DLC",
            "description": "Deliver downloadable content to the user",
            "icon": "cloud-download"
        }

    def get_handlers(self):
        return [
            (r"/bundle", handler.FetchBundleHandler),
            (r"/data/([a-z0-9_-]+)/([a-z0-9_\.-]+)", handler.AppVersionHandler),
        ]


if __name__ == "__main__":
    stt = server.init()
    access.AccessToken.init([access.public()])
    server.start(DLCServer)
