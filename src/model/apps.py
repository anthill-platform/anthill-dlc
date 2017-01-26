
from tornado.gen import coroutine, Return
from common.model import Model
from common.database import DatabaseError

import ujson


class ApplicationVersionError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class ApplicationError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class NoSuchApplicationVersionError(Exception):
    pass


class NoSuchApplicationError(Exception):
    pass


class ApplicationVersionAdapter(object):
    def __init__(self, data):
        self.name = data.get("application_name")
        self.version = data.get("application_version")
        self.gamespace_id = data.get("gamespace_id")
        self.current = data.get("current_data_version")


class ApplicationAdapter(object):
    def __init__(self, data):
        self.name = data.get("application_name")
        self.gamespace_id = data.get("gamespace_id")
        self.deployment_method = data.get("deployment_method")
        self.deployment_data = data.get("deployment_data")
        self.filters_scheme = data.get("filters_scheme", ApplicationsModel.DEFAULT_FILTERS_SCHEME)
        self.payload_scheme = data.get("payload_scheme", {})


class ApplicationsModel(Model):

    DEFAULT_PAYLOAD_SCHEME = {
        "type": "object",
        "options": {
            "disable_edit_json": True,
            "disable_properties": True
        },
        "title": "Custom Attributes",
        "properties": {

        }
    }

    DEFAULT_FILTERS_SCHEME = {
        "type": "object",
        "title": "Bundle Filters",
        "options": {
            "disable_edit_json": True,
            "disable_properties": True
        },
        "properties": {
            "architecture": {
                "type": "object",
                "title": "Architecture",
                "options": {
                    "disable_edit_json": True,
                    "disable_properties": True
                },
                "properties": {
                    "x86": {
                        "type": "boolean",
                        "title": "x86",
                        "format": "checkbox",
                        "propertyOrder": 1,
                        "default": True
                    },
                    "x64": {
                        "type": "boolean",
                        "title": "x64",
                        "format": "checkbox",
                        "propertyOrder": 2,
                        "default": True
                    },
                    "armv7": {
                        "type": "boolean",
                        "title": "armv7",
                        "format": "checkbox",
                        "propertyOrder": 3,
                        "default": True
                    },
                    "armv7s": {
                        "type": "boolean",
                        "title": "armv7s",
                        "format": "checkbox",
                        "propertyOrder": 4,
                        "default": True
                    },
                    "arm64": {
                        "type": "boolean",
                        "title": "arm64",
                        "format": "checkbox",
                        "propertyOrder": 5,
                        "default": True
                    }
                }
            },
            "os": {
                "type": "object",
                "title": "Operation System",
                "options": {
                    "disable_edit_json": True,
                    "disable_properties": True
                },
                "properties": {
                    "windows": {
                        "type": "boolean",
                        "title": "Windows",
                        "format": "checkbox",
                        "propertyOrder": 1,
                        "default": True
                    },
                    "linux": {
                        "type": "boolean",
                        "title": "Linux",
                        "format": "checkbox",
                        "propertyOrder": 2,
                        "default": True
                    },
                    "mac": {
                        "type": "boolean",
                        "title": "Mac OS X",
                        "format": "checkbox",
                        "propertyOrder": 3,
                        "default": True
                    },
                    "ios": {
                        "type": "boolean",
                        "title": "iOS",
                        "format": "checkbox",
                        "propertyOrder": 4,
                        "default": True
                    },
                    "android": {
                        "type": "boolean",
                        "title": "Android",
                        "format": "checkbox",
                        "propertyOrder": 5,
                        "default": True
                    }
                }
            }
        }
    }

    def __init__(self, db):
        self.db = db

    def get_setup_db(self):
        return self.db

    def get_setup_tables(self):
        return ["applications", "application_versions"]

    @coroutine
    def delete_application_version(self, gamespace_id, app_id, version_id):
        try:
            yield self.db.execute(
                """
                DELETE FROM `application_versions`
                WHERE `application_name`=%s AND `application_version`=%s AND `gamespace_id`=%s;
                """, app_id, version_id, gamespace_id)
        except DatabaseError as e:
            raise ApplicationVersionError("Failed to delete application version: " + e.args[1])

    @coroutine
    def find_application_version(self, gamespace_id, app_id, version_name):
        try:
            application_version = yield self.db.get(
                """
                SELECT *
                FROM `application_versions`
                WHERE `application_version`=%s AND  `application_name`=%s AND `gamespace_id`=%s;
                """, version_name, app_id, gamespace_id)
        except DatabaseError as e:
            raise ApplicationVersionError("Failed to find app version: " + e.args[1])

        if not application_version:
            raise NoSuchApplicationVersionError()

        raise Return(ApplicationVersionAdapter(application_version))

    @coroutine
    def get_application_version(self, app_id, version_id):
        try:
            application_version = yield self.db.get(
                """
                SELECT *
                FROM `application_versions`
                WHERE `application_version`=%s AND `application_name`=%s;
                """, version_id, app_id)
        except DatabaseError as e:
            raise ApplicationVersionError("Failed to get app version: " + e.args[1])

        if not application_version:
            raise NoSuchApplicationVersionError()

        raise Return(ApplicationVersionAdapter(application_version))

    @coroutine
    def switch_app_version(self, gamespace_id, app_id, version_id, data_id):

        try:
            yield self.db.insert(
                """
                INSERT INTO `application_versions`
                (`application_name`, `application_version`, `current_data_version`, `gamespace_id`)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY
                UPDATE `current_data_version`=%s;
                """, app_id, version_id, data_id, gamespace_id, data_id)
        except DatabaseError as e:
            raise ApplicationVersionError("Failed to switch app version: " + e.args[1])

    @coroutine
    def delete_application(self, gamespace_id, app_id):
        try:
            yield self.db.execute(
                """
                DELETE FROM `applications`
                WHERE `application_name`=%s AND `gamespace_id`=%s;
                """, app_id, gamespace_id)
        except DatabaseError as e:
            raise ApplicationError("Failed to delete application: " + e.args[1])

    @coroutine
    def find_application(self, gamespace_id, app_id):
        try:
            application_version = yield self.db.get(
                """
                SELECT *
                FROM `applications`
                WHERE `application_name`=%s AND `gamespace_id`=%s;
                """, app_id, gamespace_id)
        except DatabaseError as e:
            raise ApplicationError("Failed to find app version: " + e.args[1])

        if not application_version:
            raise NoSuchApplicationError()

        raise Return(ApplicationAdapter(application_version))

    @coroutine
    def get_application(self, gamespace_id, app_id):
        try:
            application_version = yield self.db.get(
                """
                SELECT *
                FROM `applications`
                WHERE `application_name`=%s AND `gamespace_id`=%s;
                """, app_id, gamespace_id)
        except DatabaseError as e:
            raise ApplicationError("Failed to get app version: " + e.args[1])

        if not application_version:
            raise NoSuchApplicationError()

        raise Return(ApplicationAdapter(application_version))

    @coroutine
    def update_application(self, gamespace_id, app_id, deployment_method,
                           deployment_data, filters_scheme, payload_scheme):

        if not isinstance(deployment_data, dict):
            raise ApplicationError("deployment_data should be a dict")

        if not isinstance(filters_scheme, dict):
            raise ApplicationError("filters_scheme should be a dict")

        if not isinstance(payload_scheme, dict):
            raise ApplicationError("payload_scheme should be a dict")

        deployment_data = ujson.dumps(deployment_data)
        filters_scheme = ujson.dumps(filters_scheme)
        payload_scheme = ujson.dumps(payload_scheme)

        try:
            yield self.db.insert(
                """
                INSERT INTO `applications`
                (`application_name`, `deployment_method`, `deployment_data`, `gamespace_id`,
                    `filters_scheme`, `payload_scheme`)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY
                UPDATE `deployment_method`=%s, `deployment_data`=%s, `filters_scheme`=%s, `payload_scheme`=%s;
                """, app_id, deployment_method, deployment_data, gamespace_id, filters_scheme, payload_scheme,
                deployment_method, deployment_data, filters_scheme, payload_scheme)
        except DatabaseError as e:
            raise ApplicationError("Failed to switch app version: " + e.args[1])


class NoSuchVersionError(Exception):
    pass


# noinspection PyUnusedLocal
class VersionExistsError(Exception):
    pass
