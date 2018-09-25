
from . apps import NoSuchApplicationError, ApplicationError
from . bundle import BundlesModel

from anthill.common.model import Model
from anthill.common.deployment import DeploymentError, DeploymentMethods


class DeploymentModel(Model):
    def __init__(self, bundles, apps):
        self.bundles = bundles
        self.apps = apps

    async def deploy(self, gamespace_id, app_id, bundles):

        try:
            settings = await self.apps.get_application(gamespace_id, app_id)
        except NoSuchApplicationError:
            raise DeploymentError("Please select deployment method first (in application settings)")
        except ApplicationError as e:
            raise DeploymentError(e.message)

        m = DeploymentMethods.get(settings.deployment_method)()
        m.load(settings.deployment_data)

        for bundle in bundles:
            if bundle.status == BundlesModel.STATUS_DELIVERED:
                continue

            await self.bundles.update_bundle_status(gamespace_id, bundle.bundle_id, BundlesModel.STATUS_DELIVERING)

            try:
                url = await m.deploy(
                    gamespace_id, self.bundles.bundle_path(app_id, bundle),
                    bundle.get_directory(), str(bundle.get_key()))
            except DeploymentError as e:
                await self.bundles.update_bundle_status(
                    gamespace_id, bundle.bundle_id, BundlesModel.STATUS_ERROR)
                raise e
            else:
                await self.bundles.update_bundle_url(
                    gamespace_id, bundle.bundle_id, BundlesModel.STATUS_DELIVERED, url)
