
from tornado.ioloop import IOLoop

from anthill.common.model import Model
from anthill.common.database import DatabaseError, ConstraintsError

from . bundle import BundlesModel
from . deploy import DeploymentError


class DataError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class VersionUsesDataError(Exception):
    pass


class NoSuchDataError(Exception):
    pass


class DataAdapter(object):
    def __init__(self, data):
        self.data_id = data["data_id"]
        self.application_name = data["application_name"]
        self.status = data["version_status"]
        self.reason = data["version_status_reason"]


class DatasModel(Model):

    STATUS_CREATED = 'CREATED'
    STATUS_PUBLISHING = 'PUBLISHING'
    STATUS_PUBLISHED = 'PUBLISHED'
    STATUS_ERROR = 'ERROR'

    def __init__(self, bundles, deployment, db):
        self.bundles = bundles
        self.deployment = deployment
        self.db = db

    def get_setup_db(self):
        return self.db

    def get_setup_tables(self):
        return ["datas"]

    async def delete_data_version(self, gamespace_id, app_id, data_id):

        try:
            exists = await self.db.get(
                """
                    SELECT *
                    FROM `application_versions`
                    WHERE `application_name`=%s AND `current_data_version`=%s
                """, app_id, data_id)
        except DatabaseError as e:
            raise DataError("Failed to get data current data version: " + e.args[1])

        if exists:
            raise VersionUsesDataError()

        data = await self.get_data_version(gamespace_id, data_id)

        if data.status == DatasModel.STATUS_PUBLISHED:
            raise DataError("Cannot delete published data version")

        bundles = await self.bundles.list_bundles(gamespace_id, data_id)

        if bundles is not None:
            for bundle in bundles:
                if bundle.status == BundlesModel.STATUS_DELIVERED:
                    continue

                await self.bundles.delete_bundle(gamespace_id, app_id, data_id, bundle.bundle_id)

        try:
            await self.db.execute(
                """
                    DELETE FROM `datas`
                    WHERE `data_id`=%s
                """, data_id)
        except ConstraintsError:
            raise VersionUsesDataError()
        except DatabaseError as e:
            raise DataError("Failed to delete data version: " + e.args[1])

    async def list_data_versions(self, gamespace_id, app_id, published=False):
        if published:
            try:
                versions = await self.db.query(
                    """
                        SELECT *
                        FROM `datas`
                        WHERE `application_name`=%s AND `gamespace_id`=%s AND `version_status`=%s;
                    """, app_id, gamespace_id, DatasModel.STATUS_PUBLISHED)
            except DatabaseError as e:
                raise DataError("Failed to list data versions: " + e.args[1])

            return map(DataAdapter, versions)
        else:
            try:
                versions = await self.db.query(
                    """
                        SELECT *
                        FROM `datas`
                        WHERE `application_name`=%s AND `gamespace_id`=%s;
                    """, app_id, gamespace_id)
            except DatabaseError as e:
                raise DataError("Failed to list data versions: " + e.args[1])

            return map(DataAdapter, versions)

    async def get_data_version(self, gamespace_id, data_id):
        try:
            version = await self.db.get(
                """
                    SELECT *
                    FROM `datas`
                    WHERE `data_id`=%s AND `gamespace_id`=%s;
                """, data_id, gamespace_id)
        except DatabaseError as e:
            raise DataError("Failed to get data version: " + e.args[1])

        if not version:
            raise NoSuchDataError()

        return DataAdapter(version)

    async def create_data_version(self, gamespace_id, app_id):

        try:
            result = await self.db.insert(
                """
                    INSERT INTO `datas`
                    (`application_name`, `version_status`, `gamespace_id`)
                    VALUES (%s, %s, %s)
                """, app_id, DatasModel.STATUS_CREATED, gamespace_id)
        except DatabaseError as e:
            raise DataError("Failed to create data version: " + e.args[1])

        return result

    async def update_data_version(self, gamespace_id, data_id, status, reason):
        try:
            await self.db.execute(
                """
                    UPDATE `datas`
                    SET `version_status`=%s, `version_status_reason`=%s
                    WHERE `data_id`=%s AND `gamespace_id`=%s
                """, status, reason, data_id, gamespace_id)
        except DatabaseError as e:
            raise DataError("Failed to create data version: " + e.args[1])

    async def publish(self, gamespace_id, data_id):

        data = await self.get_data_version(gamespace_id, data_id)

        if data.status == DatasModel.STATUS_PUBLISHED:
            raise DataError("This data version is already published")

        if data.status == DatasModel.STATUS_PUBLISHING:
            raise DataError("This data version is already being published")

        bundles = await self.bundles.list_bundles(gamespace_id, data_id)

        if not bundles:
            raise DataError("No bundles to publish")

        for bundle in bundles:
            if bundle.status not in [BundlesModel.STATUS_ERROR, BundlesModel.STATUS_UPLOADED,
                                     BundlesModel.STATUS_DELIVERED]:
                raise DataError("Bundle {0} in not uploaded yet".format(bundle.name))

        await self.update_data_version(gamespace_id, data_id, DatasModel.STATUS_PUBLISHING, "")

        async def process():
            try:
                await self.deployment.deploy(gamespace_id, data.application_name, bundles)
            except DeploymentError as e:
                await self.update_data_version(gamespace_id, data_id, DatasModel.STATUS_ERROR, e.message)
            else:
                await self.update_data_version(gamespace_id, data_id, DatasModel.STATUS_PUBLISHED, "")

        IOLoop.current().add_callback(process)
