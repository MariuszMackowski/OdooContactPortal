from odoo import models


class PortalWizardUser(models.TransientModel):
    _inherit = "portal.wizard.user"

    def action_grant_access(self):
        """
        Grants portal access to the user and ensures that the corresponding partner 
        is added as a follower of their own record if not already present.

        Returns:
            dict: The result of the parent method `action_grant_access()`.
        """
        res = super(PortalWizardUser, self).action_grant_access()
        if not self.partner_id.message_follower_ids.filtered(
            lambda follower: follower.partner_id == self.partner_id
        ):
            self.partner_id.message_follower_ids += self.env["mail.followers"].create(
                {
                    "res_model": "res.partner",
                    "res_id": self.partner_id.id,
                    "partner_id": self.partner_id.id,
                }
            )
        return res
