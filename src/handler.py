
from common.handler import JsonHandler

from tornado.gen import coroutine
from tornado.web import HTTPError, RequestHandler


class AppVersionHandler(JsonHandler):
    def data_received(self, chunk):
        pass

    @coroutine
    def get(self, app_name, version_name):

        dlc = self.application.dlc
        version_id = yield dlc.get_application_version(app_name, version_name)

        if version_id is None:
            raise HTTPError(404, "No such app and/or version")

        bundles = yield dlc.list_bundles(version_id)

        result = {}

        for bundle in bundles:
            result[bundle["bundle_name"]] = {
                "hash": bundle["bundle_hash"],
                "url": bundle["bundle_url"]
            }

        self.dumps(result)
