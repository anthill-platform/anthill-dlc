
from tornado.gen import coroutine, Return

from tornado.concurrent import run_on_executor
from concurrent.futures import ThreadPoolExecutor
from subprocess import call, CalledProcessError

from apps import NoSuchApplicationError, ApplicationError
from bundle import BundlesModel

from common.model import Model
from common.options import options

import os
import shutil
import tempfile


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
    def render(a):
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
            os.path.join(options.data_runtime_location, str(app_id), str(data.version_id), bundle.get_key()))

        return options.data_host_location + os.path.join(str(app_id), str(data.version_id), bundle.get_key())


class KeyCDNDeploymentMethod(DeploymentMethod):
    executor = ThreadPoolExecutor(max_workers=4)

    KEYCDN_RSYNC_URL = "rsync.keycdn.com"

    def __init__(self):
        super(KeyCDNDeploymentMethod, self).__init__()

        self.pri = None
        self.url = None
        self.login = None
        self.zone = None

    @staticmethod
    def render(a):
        return {
            "login": a.field("KeyCDN Username", "text", "primary", order=1),
            "zone": a.field("KeyCDN Zone Name", "text", "primary", order=2),
            "url": a.field("Public URL (including scheme)", "text", "primary", order=3),
            "pri": a.field("Private SSH Key", "text", "primary", multiline=20, order=4)
        }

    @staticmethod
    def has_admin():
        return True

    @run_on_executor
    def deploy(self, gamespace_id, app_id, data, bundle_path, bundle):

        sys_fd, path = tempfile.mkstemp()

        with open(path, 'w') as f:
            f.write(self.pri)
            f.write("\n")

        try:
            retcode = call(["rsync -avz --chmod=u=rwX,g=rX -e 'ssh -i {0}' {1} {2}@{3}:zones/{4}/{5}/".format(
                path,
                bundle_path,
                self.login,
                KeyCDNDeploymentMethod.KEYCDN_RSYNC_URL,
                self.zone,
                str(data.version_id))], shell=True)
        except CalledProcessError as e:
            raise DeploymentError("Rsync failed with code: " + str(e.returncode))
        except BaseException as e:
            raise DeploymentError(str(e))

        if retcode:
            raise DeploymentError("Rsync failed with code: " + str(retcode))

        os.close(sys_fd)

        return self.url + "/" + str(data.version_id) + "/" + str(bundle.get_key())

    @coroutine
    def update(self, pri, url, login, zone, **fields):
        self.pri = str(pri)
        self.url = str(url)
        self.login = str(login)
        self.zone = str(zone)

    def load(self, data):
        self.pri = data.get("pri")
        self.url = data.get("url")
        self.login = data.get("login")
        self.zone = data.get("zone")

    def dump(self):
        return {
            "pri": str(self.pri),
            "url": str(self.url),
            "login": str(self.login),
            "zone": str(self.zone)
        }


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
                    self.bundles.bundle_path(app_id, data.version_id, bundle), bundle)
            except DeploymentError as e:
                yield self.bundles.update_bundle_status(
                    gamespace_id, bundle.bundle_id, BundlesModel.STATUS_ERROR)
                raise e
            else:
                yield self.bundles.update_bundle_url(
                    gamespace_id, bundle.bundle_id, BundlesModel.STATUS_DELIVERED, url)