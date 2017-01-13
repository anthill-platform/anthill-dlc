import os
import hashlib

from tornado.gen import coroutine, Return
from common.model import Model
from common.database import DatabaseError

from common.options import options

class BundleError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class BundleAdapter(object):
    def __init__(self, data):
        self.bundle_id = data["bundle_id"]
        self.version = data["version_id"]
        self.name = data["bundle_name"]
        self.hash = data["bundle_hash"]
        self.url = data["bundle_url"]
        self.status = data["bundle_status"]
        self.size = data["bundle_size"]


class NoSuchBundleError(Exception):
    pass


class BundlesModel(Model):

    STATUS_CREATED = "CREATED"
    STATUS_UPLOADED = "UPLOADED"
    STATUS_DELIVERING = "DELIVERING"
    STATUS_DELIVERED = "DELIVERED"
    STATUS_ERROR = "ERROR"

    def __init__(self, db):
        self.db = db
        self.data_location = options.data_location

    def get_setup_db(self):
        return self.db

    def get_setup_tables(self):
        return ["bundles"]

    @coroutine
    def delete_bundle(self, gamespace_id, app_id, bundle_id):

        bundle = yield self.get_bundle(gamespace_id, bundle_id)
        data_id = bundle.version

        bundle_file = os.path.join(self.data_location, str(app_id), str(data_id), str(bundle_id))

        try:
            os.remove(bundle_file)
        except OSError:
            pass

        try:
            yield self.db.execute(
                """
                DELETE FROM `bundles`
                WHERE `bundle_id`=%s AND `gamespace_id`=%s;
                """, bundle_id, gamespace_id)
        except DatabaseError as e:
            raise BundleError("Failed to delete bundle: " + e.args[1])

    @coroutine
    def find_bundle(self, gamespace_id, data_id, bundle_name):
        try:
            bundle = yield self.db.get(
                """
                SELECT *
                FROM `bundles`
                WHERE `version_id`=%s AND `bundle_name`=%s AND `gamespace_id`=%s;
                """, data_id, bundle_name, gamespace_id)
        except DatabaseError as e:
            raise BundleError("Failed to find bundle: " + e.args[1])

        if not bundle:
            raise NoSuchBundleError()

        raise Return(BundleAdapter(bundle))

    @coroutine
    def get_bundle(self, gamespace_id, bundle_id):
        try:
            bundle = yield self.db.get(
                """
                SELECT *
                FROM `bundles`
                WHERE `bundle_id`=%s AND `gamespace_id`=%s;
                """, bundle_id, gamespace_id)
        except DatabaseError as e:
            raise BundleError("Failed to get bundle: " + e.args[1])

        if not bundle:
            raise NoSuchBundleError()

        raise Return(BundleAdapter(bundle))

    @coroutine
    def list_bundles(self, gamespace_id, data_id):
        try:
            bundles = yield self.db.query(
                """
                SELECT *
                FROM `bundles`
                WHERE `version_id`=%s AND `gamespace_id`=%s
                ORDER BY `bundle_id` DESC;
                """, data_id, gamespace_id)
        except DatabaseError as e:
            raise BundleError("Failed to list bundles: " + e.args[1])

        raise Return(map(BundleAdapter, bundles))

    @coroutine
    def create_bundle(self, gamespace_id, data_id, bundle_name):

        try:
            yield self.find_bundle(gamespace_id, data_id, bundle_name)
        except NoSuchBundleError:
            pass
        else:
            raise BundleError("Bundle with such name already exists")

        try:
            bundle_id = yield self.db.insert(
                """
                INSERT INTO `bundles`
                (`version_id`, `gamespace_id`, `bundle_name`, `bundle_status`)
                VALUES (%s, %s, %s, %s);
                """, data_id, gamespace_id, bundle_name, BundlesModel.STATUS_CREATED)
        except DatabaseError as e:
            raise BundleError("Failed to create bundle: " + e.args[1])

        raise Return(bundle_id)

    @coroutine
    def update_bundle(self, gamespace_id, bundle_id, bundle_hash, bundle_status, bundle_size):

        try:
            yield self.db.execute(
                """
                UPDATE `bundles`
                SET `bundle_hash`=%s, `bundle_status`=%s, `bundle_size`=%s
                WHERE `bundle_id`=%s AND `gamespace_id`=%s;
                """, bundle_hash, bundle_status, bundle_size, bundle_id, gamespace_id)
        except DatabaseError as e:
            raise BundleError("Failed to update bundle: " + e.args[1])

    @coroutine
    def update_bundle_status(self, gamespace_id, bundle_id, bundle_status):

        try:
            yield self.db.execute(
                """
                UPDATE `bundles`
                SET `bundle_status`=%s
                WHERE `bundle_id`=%s AND `gamespace_id`=%s;
                """, bundle_status, bundle_id, gamespace_id)
        except DatabaseError as e:
            raise BundleError("Failed to update bundle status: " + e.args[1])

    @coroutine
    def update_bundle_url(self, gamespace_id, bundle_id, bundle_status, bundle_url):

        try:
            yield self.db.execute(
                """
                UPDATE `bundles`
                SET `bundle_status`=%s, `bundle_url`=%s
                WHERE `bundle_id`=%s AND `gamespace_id`=%s;
                """, bundle_status, bundle_url, bundle_id, gamespace_id)
        except DatabaseError as e:
            raise BundleError("Failed to update bundle status: " + e.args[1])

    def bundle_path(self, app_id, data_id, bundle_id):
        return os.path.join(self.data_location, str(app_id), str(data_id), str(bundle_id))

    def bundle_directory(self, app_id, data_id):
        return os.path.join(self.data_location, str(app_id), str(data_id))

    @coroutine
    def upload_bundle(self, gamespace_id, app_id, data_id, bundle_name, producer):

        try:
            bundle = yield self.find_bundle(gamespace_id, data_id, bundle_name)
        except NoSuchBundleError:
            bundle_id = yield self.create_bundle(data_id, gamespace_id, bundle_name)
        else:
            bundle_id = bundle.bundle_id

        if not os.path.exists(self.bundle_directory(app_id, data_id)):
            os.makedirs(self.bundle_directory(app_id, data_id))

        bundle_file = self.bundle_path(app_id, data_id, bundle_id)

        md5 = hashlib.md5()
        output_file = open(bundle_file, 'wb')

        class Size:
            bundle_size = 0

        @coroutine
        def write(data):
            output_file.write(data)
            md5.update(data)
            Size.bundle_size += len(data)

        yield producer(write)

        output_file.close()

        bundle_hash = md5.hexdigest()

        yield self.update_bundle(
            gamespace_id, bundle_id, bundle_hash, BundlesModel.STATUS_UPLOADED, Size.bundle_size)
