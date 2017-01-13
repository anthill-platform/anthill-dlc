
from tornado.gen import coroutine, Return

from tornado.concurrent import run_on_executor
from concurrent.futures import ThreadPoolExecutor

from apps import NoSuchApplicationError, ApplicationError
from bundle import BundlesModel

from common.model import Model
from common.options import options

import os
import shutil


class DeploymentError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class DeploymentMethod(object):
    @coroutine
    def deploy(self, gamespace_id, app_id, data, bundle_path, bundle):
        raise NotImplementedError()

    def dump(self):
        return {}

    def load(self, data):
        pass

    @staticmethod
    def render():
        return {}

    @coroutine
    def update(self, **fields):
        pass

    @staticmethod
    def has_admin():
        return False


class LocalDeploymentMethod(DeploymentMethod):
    executor = ThreadPoolExecutor(max_workers=4)

    @run_on_executor
    def deploy(self, gamespace_id, app_id, data, bundle_path, bundle):

        target_dir = os.path.join(options.data_runtime_location, str(app_id), str(data.version_id))

        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        shutil.copyfile(bundle_path,
            os.path.join(options.data_runtime_location, str(app_id), str(data.version_id), str(bundle.bundle_id)))

        return options.data_host_location + os.path.join(str(app_id), str(data.version_id), str(bundle.bundle_id))


class KeyCDNDeploymentMethod(DeploymentMethod):
    @staticmethod
    def render():
        return {

        }

    @staticmethod
    def has_admin():
        return True

    @coroutine
    def deploy(self, gamespace_id, app_id, data, bundle_path, bundle):
        raise Return("KKK")

    @coroutine
    def update(self, **fields):
        pass

    def load(self, data):
        pass

    def dump(self):
        return {}


class DeploymentMethods(object):
    METHODS = {
        "local": LocalDeploymentMethod,
        "keycdn": KeyCDNDeploymentMethod
    }

    @staticmethod
    def valid(method):
        return method in DeploymentMethods.METHODS

    @staticmethod
    def types():
        return DeploymentMethods.METHODS.keys()

    @staticmethod
    def get(method):
        return DeploymentMethods.METHODS.get(method)


class DeploymentModel(Model):
    def __init__(self, bundles, apps):
        self.bundles = bundles
        self.apps = apps

    @coroutine
    def deploy(self, gamespace_id, app_id, data, bundles):

        try:
            settings = yield self.apps.get_application(gamespace_id, app_id)
        except NoSuchApplicationError:
            raise DeploymentError("Please select deployment method first (in application settings)")
        except ApplicationError as e:
            raise DeploymentError(e.message)

        m = DeploymentMethods.get(settings.deployment_method)()
        m.load(settings.deployment_data)

        for bundle in bundles:
            yield self.bundles.update_bundle_status(gamespace_id, bundle.bundle_id, BundlesModel.STATUS_DELIVERING)

            try:
                url = yield m.deploy(
                    gamespace_id, app_id, data,
                    self.bundles.bundle_path(app_id, data.version_id, bundle.bundle_id), bundle)
            except DeploymentError as e:
                yield self.bundles.update_bundle_status(
                    gamespace_id, bundle.bundle_id, BundlesModel.STATUS_ERROR)
                raise e
            else:
                yield self.bundles.update_bundle_url(
                    gamespace_id, bundle.bundle_id, BundlesModel.STATUS_DELIVERED, url)