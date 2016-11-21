import os
import hashlib

from tornado.gen import coroutine, Return
from common.model import Model
from common.database import DatabaseError, ConstraintsError


class DLCError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class VersionUsesDataError(Exception):
    pass


class DLCModel(Model):
    def __init__(self, db):
        self.db = db

    def get_setup_db(self):
        return self.db

    def get_setup_tables(self):
        return ["data_versions", "bundles", "application_versions"]

    @coroutine
    def delete_application_version(self, app_id, version_id):
        try:
            yield self.db.execute(
                """
                DELETE FROM `application_versions`
                WHERE `application_name`=%s AND `application_version`=%s;
                """, app_id, version_id)
        except DatabaseError as e:
            raise DLCError("Failed to delete application version: " + e.args[1])

    @coroutine
    def delete_bundle(self, app_id, data_id, bundle_id, data_location):

        bundle_file = os.path.join(data_location, str(app_id), str(data_id), str(bundle_id))

        try:
            os.remove(bundle_file)
        except OSError:
            pass

        try:
            yield self.db.execute(
                """
                DELETE FROM `bundles`
                WHERE `bundle_id`=%s;
                """, bundle_id)
        except DatabaseError as e:
            raise DLCError("Failed to delete bundle: " + e.args[1])

    @coroutine
    def delete_data_version(self, app_id, data_id, data_location):

        try:
            exists = yield self.db.get(
                """
                SELECT *
                FROM `application_versions`
                WHERE `application_name`=%s AND `current_data_version`=%s
                """, app_id, data_id)
        except DatabaseError as e:
            raise DLCError("Failed to get data current data version: " + e.args[1])

        if exists:
            raise VersionUsesDataError()

        bundles = yield self.list_bundles(data_id)

        if bundles is not None:
            for bundle in bundles:
                yield self.delete_bundle(app_id, data_id, bundle["bundle_id"], data_location)

        try:
            yield self.db.execute(
                """
                DELETE FROM `data_versions`
                WHERE `version_id`=%s
                """, data_id)
        except ConstraintsError:
            raise VersionUsesDataError()
        except DatabaseError as e:
            raise DLCError("Failed to delete data version: " + e.args[1])

    @coroutine
    def find_application_version(self, app_id, version_name):
        try:
            app = yield self.db.get(
                """
                SELECT *
                FROM `application_versions`
                WHERE `application_version`=%s AND  `application_name`=%s;
                """, version_name, app_id)
        except DatabaseError as e:
            raise DLCError("Failed to find app version: " + e.args[1])

        raise Return(app)

    @coroutine
    def find_bundle(self, data_id, bundle_name):
        try:
            bundle = yield self.db.get(
                """
                SELECT *
                FROM `bundles`
                WHERE `version_id`=%s AND `bundle_name`=%s;
                """, data_id, bundle_name)
        except DatabaseError as e:
            raise DLCError("Failed to find bundle: " + e.args[1])

        raise Return(bundle)

    @coroutine
    def get_application_version(self, app_id, version_id):
        try:
            app = yield self.db.get(
                """
                SELECT `current_data_version`
                FROM `application_versions`
                WHERE `application_version`=%s AND `application_name`=%s;
                """, version_id, app_id)
        except DatabaseError as e:
            raise DLCError("Failed to get app version: " + e.args[1])

        if app:
            raise Return(app["current_data_version"])

        raise Return(None)

    @coroutine
    def get_bundle(self, data_id, bundle_id):
        try:
            bundle = yield self.db.get(
                """
                SELECT *
                FROM `bundles`
                WHERE `version_id`=%s AND `bundle_id`=%s;
                """, data_id, bundle_id)
        except DatabaseError as e:
            raise DLCError("Failed to get bundle: " + e.args[1])

        raise Return(bundle)

    @coroutine
    def list_bundles(self, data_id):
        try:
            bundles = yield self.db.query(
                """
                SELECT *
                FROM `bundles`
                WHERE `version_id`=%s
                """, data_id)
        except DatabaseError as e:
            raise DLCError("Failed to list bundles: " + e.args[1])

        raise Return(bundles)

    @coroutine
    def list_data_versions(self, app_id):
        try:
            versions = yield self.db.query(
                """
                SELECT *
                FROM `data_versions`
                WHERE `application_name`=%s
                """, app_id)
        except DatabaseError as e:
            raise DLCError("Failed to list data versions: " + e.args[1])

        raise Return(versions)

    @coroutine
    def create_application_version(self, app_id, version_name, data_id):
        v = yield self.find_application_version(app_id, version_name)
        if v:
            raise VersionExistsError()

        try:
            result = yield self.db.insert(
                """
                INSERT INTO `application_versions`
                (`application_name`, `application_version`, `current_data_version`)
                VALUES (%s, %s, %s);
                """, app_id, version_name, data_id)
        except DatabaseError as e:
            raise DLCError("Failed to create application version: " + e.args[1])

        raise Return(result)

    @coroutine
    def create_bundle(self, data_id, bundle_name):

        try:
            result = yield self.db.insert(
                """
                INSERT INTO `bundles`
                (`version_id`, `bundle_name`)
                VALUES (%s, %s);
                """, data_id, bundle_name)
        except DatabaseError as e:
            raise DLCError("Failed to create bundle: " + e.args[1])

        raise Return(result)

    @coroutine
    def create_data_version(self, app_id):

        try:
            result = yield self.db.insert(
                """
                INSERT INTO `data_versions`
                (`application_name`, `version_status`)
                VALUES (%s, 'created')
                """, app_id)
        except DatabaseError as e:
            raise DLCError("Failed to create data version: " + e.args[1])

        raise Return(result)

    @coroutine
    def switch_app_version(self, app_id, version_id, data_id):

        if (yield self.get_application_version(app_id, version_id)):
            try:
                yield self.db.execute(
                    """
                    UPDATE `application_versions`
                    SET `current_data_version`=%s
                    WHERE `application_name`=%s AND `application_version`=%s;
                    """, data_id, version_id, app_id)
            except DatabaseError as e:
                raise DLCError("Failed to update app version: " + e.args[1])
        else:
            try:
                yield self.db.insert(
                    """
                    INSERT INTO `application_versions`
                    (`application_name`, `application_version`, `current_data_version`)
                    VALUES (%s, %s, %s);
                    """, app_id, version_id, data_id)
            except DatabaseError as e:
                raise DLCError("Failed to create app version: " + e.args[1])

    @coroutine
    def upload_bundle(self, app_id, data_id, bundle_name, data_location, host_location, producer):

        bundle = yield self.find_bundle(data_id, bundle_name)

        if bundle is None:
            bundle_id = yield self.create_bundle(data_id, bundle_name)
        else:
            bundle_id = bundle["bundle_id"]

        if not os.path.exists(os.path.join(data_location, str(app_id), str(data_id))):
            os.makedirs(os.path.join(data_location, str(app_id), str(data_id)))

        bundle_file = os.path.join(data_location, str(app_id), str(data_id), str(bundle_id))

        md5 = hashlib.md5()
        output_file = open(bundle_file, 'wb')

        @coroutine
        def write(data):
            output_file.write(data)
            md5.update(data)

        yield producer(write)

        output_file.close()

        bundle_hash = md5.hexdigest()
        bundle_url = host_location + os.path.join(str(app_id), str(data_id), str(bundle_id))

        try:
            yield self.db.execute(
                """
                UPDATE `bundles`
                SET `bundle_hash`=%s, `bundle_url`=%s
                WHERE `bundle_id`=%s;
                """, bundle_hash, bundle_url, bundle_id)
        except DatabaseError as e:
            raise DLCError("Failed to update bundle: " + e.args[1])


class NoSuchVersionError(Exception):
    pass


# noinspection PyUnusedLocal
class VersionExistsError(Exception):
    pass


