# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2010-today OpenERP SA (<http://www.openerp.com>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>
#
##############################################################################

import base64
import logging
import re
from urllib import urlencode
from urlparse import urljoin

from openerp import tools
from openerp import SUPERUSER_ID
from openerp.osv import fields, osv
from openerp.osv.orm import except_orm
from openerp.tools.translate import _

_logger = logging.getLogger(__name__)


class mail_mail(osv.Model):
    """ Model holding RFC2822 email messages to send. This model also provides
        facilities to queue and send new email messages.  """
    _name = 'mail.mail'
    _description = 'Outgoing Mails'
    _inherits = {'mail.message': 'mail_message_id'}
    _order = 'id desc'

    _columns = {
        'mail_message_id': fields.many2one('mail.message', 'Message', required=True, ondelete='cascade'),
        'mail_server_id': fields.many2one('ir.mail_server', 'Outgoing mail server', readonly=1),
        'state': fields.selection([
            ('outgoing', 'Outgoing'),
            ('sent', 'Sent'),
            ('received', 'Received'),
            ('exception', 'Delivery Failed'),
            ('cancel', 'Cancelled'),
        ], 'Status', readonly=True),
        'auto_delete': fields.boolean('Auto Delete',
            help="Permanently delete this email after sending it, to save space"),
        'references': fields.text('References', help='Message references, such as identifiers of previous messages', readonly=1),
        'email_from': fields.char('From', help='Message sender, taken from user preferences.'),
        'email_to': fields.text('To', help='Message recipients (emails)'),
        'recipient_ids': fields.many2many('res.partner', string='To (Partners)'),
        'email_cc': fields.char('Cc', help='Carbon copy message recipients'),
        'body_html': fields.text('Rich-text Contents', help="Rich-text/HTML message"),
        # If not set in create values, auto-detected based on create values (res_id, model, email_from)
        'reply_to': fields.char('Reply-To',
            help='Preferred response address for the message'),
        # Auto-detected based on create() - if 'mail_message_id' was passed then this mail is a notification
        # and during unlink() we will not cascade delete the parent and its attachments
        'notification': fields.boolean('Is Notification',
            help='Mail has been created to notify people of an existing mail.message')
    }

    def _get_default_from(self, cr, uid, context=None):
        this = self.pool.get('res.users').browse(cr, SUPERUSER_ID, uid, context=context)
        if this.alias_domain:
            return '%s <%s@%s>' % (this.name, this.alias_name, this.alias_domain)
        elif this.email:
            return '%s <%s>' % (this.name, this.email)
        raise osv.except_osv(_('Invalid Action!'), _("Unable to send email, please configure the sender's email address or alias."))

    _defaults = {
        'state': 'outgoing',
        'email_from': lambda self, cr, uid, ctx=None: self._get_default_from(cr, uid, ctx),
    }

    def default_get(self, cr, uid, fields, context=None):
        # protection for `default_type` values leaking from menu action context (e.g. for invoices)
        # To remove when automatic context propagation is removed in web client
        if context and context.get('default_type') and context.get('default_type') not in self._all_columns['type'].column.selection:
            context = dict(context, default_type=None)
        return super(mail_mail, self).default_get(cr, uid, fields, context=context)

    def _get_reply_to(self, cr, uid, values, context=None):
        """ Return a specific reply_to: alias of the document through message_get_reply_to
            or take the email_from
        """
        if values.get('reply_to'):
            return values.get('reply_to')
        email_reply_to = False

        # model, res_id: comes from values OR related message
        model = values.get('model')
        res_id = values.get('res_id')
        if values.get('mail_message_id') and (not model or not res_id):
            message = self.pool.get('mail.message').browse(cr, uid, values.get('mail_message_id'), context=context)
            if not model:
                model = message.model
            if not res_id:
                res_id = message.res_id

        # if model and res_id: try to use ``message_get_reply_to`` that returns the document alias
        if model and res_id and hasattr(self.pool.get(model), 'message_get_reply_to'):
            email_reply_to = self.pool.get(model).message_get_reply_to(cr, uid, [res_id], context=context)[0]
        # no alias reply_to -> reply_to will be the email_from, only the email part
        if not email_reply_to and values.get('email_from'):
            emails = tools.email_split(values.get('email_from'))
            if emails:
                email_reply_to = emails[0]

        # format 'Document name <email_address>'
        if email_reply_to and model and res_id:
            document_name = self.pool.get(model).name_get(cr, SUPERUSER_ID, [res_id], context=context)[0]
            if document_name:
                # sanitize document name
                sanitized_doc_name = re.sub(r'[^\w+.]+', '-', document_name[1])
                # generate reply to
                email_reply_to = _('"Followers of %s" <%s>') % (sanitized_doc_name, email_reply_to)

        return email_reply_to

    def create(self, cr, uid, values, context=None):
        # notification field: if not set, set if mail comes from an existing mail.message
        if 'notification' not in values and values.get('mail_message_id'):
            values['notification'] = True
        # reply_to: if not set, set with default values that require creation values
        if not values.get('reply_to'):
            values['reply_to'] = self._get_reply_to(cr, uid, values, context=context)
        return super(mail_mail, self).create(cr, uid, values, context=context)

    def unlink(self, cr, uid, ids, context=None):
        # cascade-delete the parent message for all mails that are not created for a notification
        ids_to_cascade = self.search(cr, uid, [('notification', '=', False), ('id', 'in', ids)])
        parent_msg_ids = [m.mail_message_id.id for m in self.browse(cr, uid, ids_to_cascade, context=context)]
        res = super(mail_mail, self).unlink(cr, uid, ids, context=context)
        self.pool.get('mail.message').unlink(cr, uid, parent_msg_ids, context=context)
        return res

    def mark_outgoing(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'outgoing'}, context=context)

    def cancel(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'cancel'}, context=context)

    def process_email_queue(self, cr, uid, ids=None, context=None):
        """Send immediately queued messages, committing after each
           message is sent - this is not transactional and should
           not be called during another transaction!

           :param list ids: optional list of emails ids to send. If passed
                            no search is performed, and these ids are used
                            instead.
           :param dict context: if a 'filters' key is present in context,
                                this value will be used as an additional
                                filter to further restrict the outgoing
                                messages to send (by default all 'outgoing'
                                messages are sent).
        """
        if context is None:
            context = {}
        if not ids:
            filters = ['&', ('state', '=', 'outgoing'), ('type', '=', 'email')]
            if 'filters' in context:
                filters.extend(context['filters'])
            ids = self.search(cr, uid, filters, context=context)
        res = None
        try:
            # Force auto-commit - this is meant to be called by
            # the scheduler, and we can't allow rolling back the status
            # of previously sent emails!
            res = self.send(cr, uid, ids, auto_commit=True, context=context)
        except Exception:
            _logger.exception("Failed processing mail queue")
        return res

    def _postprocess_sent_message(self, cr, uid, mail, context=None):
        """Perform any post-processing necessary after sending ``mail``
        successfully, including deleting it completely along with its
        attachment if the ``auto_delete`` flag of the mail was set.
        Overridden by subclasses for extra post-processing behaviors.

        :param browse_record mail: the mail that was just sent
        :return: True
        """
        if mail.auto_delete:
            # done with SUPERUSER_ID to avoid giving large unlink access rights
            self.unlink(cr, SUPERUSER_ID, [mail.id], context=context)
        return True

    def send_get_mail_subject(self, cr, uid, mail, force=False, partner=None, context=None):
        """ If subject is void and record_name defined: '<Author> posted on <Resource>'

            :param boolean force: force the subject replacement
            :param browse_record mail: mail.mail browse_record
            :param browse_record partner: specific recipient partner
        """
        if force or (not mail.subject and mail.model and mail.res_id):
            return 'Re: %s' % (mail.record_name)
        return mail.subject

    def send_get_mail_body_footer(self, cr, uid, mail, partner=None, context=None):
        """ Return a specific footer for the ir_email body.  The main purpose of this method
            is to be inherited by Portal, to add modify the link for signing in, in
            each notification email a partner receives.
        """
        body_footer = ""
        # partner is a user, link to a related document (incentive to install portal)
        if partner and partner.user_ids and mail.model and mail.res_id \
                and self.check_access_rights(cr, partner.user_ids[0].id, 'read', raise_exception=False):
            related_user = partner.user_ids[0]
            try:
                self.pool.get(mail.model).check_access_rule(cr, related_user.id, [mail.res_id], 'read', context=context)
                base_url = self.pool.get('ir.config_parameter').get_param(cr, uid, 'web.base.url')
                # the parameters to encode for the query and fragment part of url
                query = {'db': cr.dbname}
                fragment = {
                    'login': related_user.login,
                    'model': mail.model,
                    'id': mail.res_id,
                }
                url = urljoin(base_url, "?%s#%s" % (urlencode(query), urlencode(fragment)))
                body_footer = _("""<small>Access this document <a style='color:inherit' href="%s">directly in OpenERP</a></small>""") % url
            except except_orm, e:
                pass
        return body_footer

    def send_get_mail_body(self, cr, uid, mail, partner=None, context=None):
        """ Return a specific ir_email body. The main purpose of this method
            is to be inherited to add custom content depending on some module.

            :param browse_record mail: mail.mail browse_record
            :param browse_record partner: specific recipient partner
        """
        body = mail.body_html

        # add footer
        body_footer = self.send_get_mail_body_footer(cr, uid, mail, partner=partner, context=context)
        body = tools.append_content_to_html(body, body_footer, plaintext=False, container_tag='div')
        return body

    def send_get_email_dict(self, cr, uid, mail, partner=None, context=None):
        """ Return a dictionary for specific email values, depending on a
            partner, or generic to the whole recipients given by mail.email_to.

            :param browse_record mail: mail.mail browse_record
            :param browse_record partner: specific recipient partner
        """
        body = self.send_get_mail_body(cr, uid, mail, partner=partner, context=context)
        subject = self.send_get_mail_subject(cr, uid, mail, partner=partner, context=context)
        body_alternative = tools.html2plaintext(body)
        email_to = ['%s <%s>' % (partner.name, partner.email)] if partner else tools.email_split(mail.email_to)
        return {
            'body': body,
            'body_alternative': body_alternative,
            'subject': subject,
            'email_to': email_to,
        }

    def send(self, cr, uid, ids, auto_commit=False, context=None):
        """ Sends the selected emails immediately, ignoring their current
            state (mails that have already been sent should not be passed
            unless they should actually be re-sent).
            Emails successfully delivered are marked as 'sent', and those
            that fail to be deliver are marked as 'exception', and the
            corresponding error mail is output in the server logs.

            :param bool auto_commit: whether to force a commit of the mail status
                after sending each mail (meant only for scheduler processing);
                should never be True during normal transactions (default: False)
            :return: True
        """
        ir_mail_server = self.pool.get('ir.mail_server')
        for mail in self.browse(cr, SUPERUSER_ID, ids, context=context):
            try:
                # handle attachments
                attachments = []
                for attach in mail.attachment_ids:
                    attachments.append((attach.datas_fname, base64.b64decode(attach.datas)))
                # specific behavior to customize the send email for notified partners
                email_list = []
                if mail.email_to:
                    email_list.append(self.send_get_email_dict(cr, uid, mail, context=context))
                for partner in mail.recipient_ids:
                    email_list.append(self.send_get_email_dict(cr, uid, mail, partner=partner, context=context))

                # build an RFC2822 email.message.Message object and send it without queuing
                for email in email_list:
                    msg = ir_mail_server.build_email(
                        email_from = mail.email_from,
                        email_to = email.get('email_to'),
                        subject = email.get('subject'),
                        body = email.get('body'),
                        body_alternative = email.get('body_alternative'),
                        email_cc = tools.email_split(mail.email_cc),
                        reply_to = mail.reply_to,
                        attachments = attachments,
                        message_id = mail.message_id,
                        references = mail.references,
                        object_id = mail.res_id and ('%s-%s' % (mail.res_id, mail.model)),
                        subtype = 'html',
                        subtype_alternative = 'plain')
                    res = ir_mail_server.send_email(cr, uid, msg,
                        mail_server_id=mail.mail_server_id.id, context=context)
                if res:
                    mail.write({'state': 'sent', 'message_id': res})
                    mail_sent = True
                else:
                    mail.write({'state': 'exception'})
                    mail_sent = False

                # /!\ can't use mail.state here, as mail.refresh() will cause an error
                # see revid:odo@openerp.com-20120622152536-42b2s28lvdv3odyr in 6.1
                if mail_sent:
                    self._postprocess_sent_message(cr, uid, mail, context=context)
            except Exception:
                _logger.exception('failed sending mail.mail %s', mail.id)
                mail.write({'state': 'exception'})

            if auto_commit == True:
                cr.commit()
        return True
