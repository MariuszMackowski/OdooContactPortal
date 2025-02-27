from odoo import http, _
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.portal.controllers import portal
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.osv import expression


class CustomerPortal(portal.CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        """
        Adds the contact count to the home portal counters and returns the updated dictionary with portal values.
        
        Args:
            counters (dict): A dictionary containing the existing counters to be included in the home portal.

        Returns:
            dict: A dictionary with the updated portal values, including the `contact_count` if the user has access rights.
        """
        values = super()._prepare_home_portal_values(counters)

        Partner = request.env["res.partner"]
        if "contact_count" in counters:
            values["contact_count"] = (
                Partner.search_count(self._prepare_contact_domain())
                if Partner.check_access_rights("read", raise_exception=False)
                else 0
            )
        return values

    def _prepare_contact_domain(self):
        """
        Returns a domain expression used for filtering contacts based on the user's company and access level.
        
        Returns:
            list: A list representing the domain expression used for filtering contacts:
                - For portal users: Filters contacts by company (parent company) and excludes self.
                - For internal users: Allows all contacts to be viewed.
        """
        user = request.env.user
        domain = [
            "&",
            ("type", "in", ["contact", "other"]), # Doesn't make sens to send message to invoice/delivery address
            ("id", "!=", user.partner_id.id), # Filter self
        ]
        
        if user.has_group("base.group_user"):
            return domain  # If Portal users should only see contacts from their own company, internal users can see all the contacts?

        parent_company_id = user.partner_id.parent_id.id

        return expression.AND(
            [
                domain,
                [
                    "|",
                    "&",
                    ("parent_id", "=", parent_company_id),  # Other company employees                    
                    ("parent_id", "!=", False),  # Filter contacts without parent_id
                    ("id","=",parent_company_id,),  # Should user see company's main contact?
                ],
            ]
        )

    def _get_contact_searchbar_sortings(self):
        """
        Returns the available sorting options for the contact search bar in the portal. 
        
        Returns:
            dict: A dictionary containing sorting options for contacts:
                - "name": Sorts by name in ascending order.
                - "date": Sorts by the creation date in descending order.
                Each option is represented by a label (translated) and the corresponding order for sorting.
        """

        return {
            "name": {"label": _("Name"), "order": "name"},
            "date": {"label": _("Creation Date"), "order": "create_date desc"},
        }

    def _prepare_contact_portal_rendering_values(
        self,
        page=1,
        sortby="name",
        **kwargs,
    ):
        """
        Prepares the values required for rendering the user's contact page in the portal. This method handles pagination, filtering by date range, and sorting of contacts. It returns the necessary data for the portal view, including the list of contacts, pagination details, and sorting options.

        Args:
            page (int, optional): The page number for pagination (default is 1).
            sortby (str, optional): The field by which contacts should be sorted (default is "name").
            **kwargs: Any additional parameters that might be passed in the URL (such as filtering options).

        Returns:
            dict: A dictionary containing the data to be rendered in the portal view, including:
                - contacts (recordset): A list of contacts (`res.partner`) based on the search domain and pagination.
                - pager (dict): Pagination information.
                - searchbar_sortings (dict): Available sorting options for the search bar.
                - sortby (str): The current sorting field.
        """

        Contact = request.env["res.partner"]

        if not sortby:
            sortby = "date"
        values = self._prepare_portal_layout_values()

        url = "/my/contacts"
        domain = self._prepare_contact_domain()

        searchbar_sortings = self._get_contact_searchbar_sortings()

        sort_order = searchbar_sortings[sortby]["order"]

        pager_values = portal_pager(
            url=url,
            total=Contact.search_count(domain),
            page=page,
            step=self._items_per_page,
            url_args={"sortby": sortby},
        )
        contacts_sudo = Contact.search(
            domain,
            order=sort_order,
            limit=self._items_per_page,
            offset=pager_values["offset"],
        )
        values.update(
            {
                "contacts": contacts_sudo,
                "page_name": "contacts",
                "pager": pager_values,
                "default_url": url,
                "searchbar_sortings": searchbar_sortings,
                "sortby": sortby,
            }
        )

        return values

    @http.route(
        ["/my/contacts", "/my/contacts/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_contacts(self, **kwargs):
        """
        Handles the rendering of the user's contact page in the portal. This method is responsible for preparing the necessary data for displaying the user's contacts and rendering the appropriate template.

        Args:
            **kwargs: Any additional parameters that might be passed in the URL.

        Returns:
            werkzeug.Response: The rendered portal page displaying the user's contacts, using the template `contact_portal.portal_my_contacts`.
        """

        values = self._prepare_contact_portal_rendering_values(**kwargs)
        request.session["my_contact_history"] = values["contacts"].ids[:100]
        return request.render("contact_portal.portal_my_contacts", values)

    @http.route(
        ["/my/contacts/<int:contact_id>"], type="http", auth="public", website=True
    )
    def portal_contact_page(
        self,
        contact_id,
        access_token=None,
        message=False,
        **kw,
    ):
        """
        Handles access to a contact's details (`res.partner`) in the user portal, checking permissions and generating a backend URL for Odoo. If the user does not have access, they are redirected to the `/my` page.

        Args:
            contact_id (int): The ID of the contact (`res.partner`) to which the user is requesting access.
            access_token (str): The access token used to verify the user's permissions (optional).
            message (str): An optional message to display on the page.

        Returns:
            werkzeug.Response: A rendered portal page with contact details or a redirect to `/my` if access is denied.
        """
        try:
            contact_sudo = self._document_check_access(
                "res.partner", contact_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return request.redirect("/my")

        backend_url = (
            f"/web#model={contact_sudo._name}"
            f"&id={contact_sudo.id}"
            f"&view_type=form"
        )
        values = {
            "contact": contact_sudo,
            "message": message,
            "report_type": "html",
            "backend_url": backend_url,
        }

        history_session_key = "my_quest_history"

        values = self._get_page_view_values(
            contact_sudo, access_token, values, history_session_key, False
        )

        return request.render("contact_portal.contact_portal_template", values)
