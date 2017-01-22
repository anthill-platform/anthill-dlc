
from common.handler import JsonHandler, AuthenticatedHandler
from common.access import scoped, AccessToken

from tornado.gen import coroutine
from tornado.web import HTTPError

from model.apps import NoSuchApplicationVersionError, ApplicationVersionError
from model.bundle import BundleQueryError, BundlesModel

import ujson


class AppVersionHandler(JsonHandler):
    def data_received(self, chunk):
        pass

    @coroutine
    def get(self, app_name, version_name):

        apps = self.application.app_versions
        bundles = self.application.bundles

        env = self.get_argument("env", "{}")

        try:
            env = ujson.loads(env)
        except (KeyError, ValueError):
            raise HTTPError(400, "Corrupted 'env'")

        try:
            v = yield apps.get_application_version(app_name, version_name)
        except NoSuchApplicationVersionError:
            raise HTTPError(404, "No such app and/or version")
        except ApplicationVersionError as e:
            raise HTTPError(500, e.message)

        q = bundles.bundles_query(v.gamespace_id)

        q.data_id = v.current
        q.status = BundlesModel.STATUS_DELIVERED
        q.filters = env

        try:
            bundles = yield q.query(one=False)
        except BundleQueryError as e:
            raise HTTPError(500, e.message)

        self.dumps({
            "bundles": {
                bundle.name: {
                    "hash": bundle.hash,
                    "url": bundle.url,
                    "size": bundle.size,
                    "payload": bundle.payload
                } for bundle in bundles
            }
        })


class FetchBundleHandler(AuthenticatedHandler):
    @scoped(scopes=["dlc"])
    @coroutine
    def get(self):

        apps = self.application.app_versions
        bundles = self.application.bundles

        bundle_name = self.get_argument("bundle_name")
        bundle_hash = self.get_argument("bundle_hash")

        gamespace_id = self.current_user.token.get(AccessToken.GAMESPACE)

        q = bundles.bundles_query(gamespace_id)

        q.status = BundlesModel.STATUS_DELIVERED
        q.name = bundle_name
        q.hash = bundle_hash

        try:
            bundle = yield q.query(one=True)
        except BundleQueryError as e:
            raise HTTPError(500, e.message)

        if not bundle:
            raise HTTPError(404, "No such bundle")

        self.dumps({
            "bundle": {
                "hash": bundle.hash,
                "url": bundle.url,
                "size": bundle.size,
                "payload": bundle.payload
            }
        })
