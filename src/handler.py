
from common.handler import JsonHandler

from tornado.gen import coroutine
from tornado.web import HTTPError

from model.apps import NoSuchApplicationVersionError, ApplicationVersionError


class AppVersionHandler(JsonHandler):
    def data_received(self, chunk):
        pass

    @coroutine
    def get(self, app_name, version_name):

        apps = self.application.app_versions
        bundles = self.application.bundles

        try:
            v = yield apps.get_application_version(app_name, version_name)
        except NoSuchApplicationVersionError:
            raise HTTPError(404, "No such app and/or version")
        except ApplicationVersionError as e:
            raise HTTPError(500, e.message)

        bundles = yield bundles.list_bundles(v.gamespace_id, v.current)

        result = {}

        for bundle in bundles:
            result[bundle.name] = {
                "hash": bundle.hash,
                "url": bundle.url,
                "size": bundle.size
            }

        self.dumps(result)
