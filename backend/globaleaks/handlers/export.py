# -*- coding: utf-8 -*-
#
# API handling export of submissions
import os

from io import BytesIO
from twisted.internet import abstract
from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.internet.threads import deferToThread

from globaleaks import models
from globaleaks.handlers.admin.context import admin_serialize_context
from globaleaks.handlers.admin.node import db_admin_serialize_node
from globaleaks.handlers.admin.notification import db_get_notification
from globaleaks.handlers.admin.submission_statuses import db_retrieve_all_submission_statuses
from globaleaks.handlers.base import BaseHandler
from globaleaks.handlers.rtip import db_access_rtip, serialize_rtip
from globaleaks.handlers.submission import decrypt_tip
from globaleaks.handlers.user import user_serialize_user
from globaleaks.orm import transact
from globaleaks.settings import Settings
from globaleaks.utils.crypto import GCE
from globaleaks.utils.templating import Templating
from globaleaks.utils.utility import msdos_encode, datetime_now
from globaleaks.utils.zipstream import ZipStream


@transact
def get_tip_export(session, tid, user_id, rtip_id, language):
    rtip, itip = db_access_rtip(session, tid, user_id, rtip_id)

    user, context = session.query(models.User, models.Context) \
                           .filter(models.User.id == rtip.receiver_id,
                                   models.Context.id == models.InternalTip.context_id,
                                   models.InternalTip.id == rtip.internaltip_id,
                                   models.User.tid == tid).one()

    rtip_dict = serialize_rtip(session, rtip, itip, language)

    export_dict = {
        'type': 'export_template',
        'node': db_admin_serialize_node(session, tid, language),
        'notification': db_get_notification(session, tid, language),
        'tip': rtip_dict,
        'crypto_tip_prv_key': rtip.crypto_tip_prv_key,
        'user': user_serialize_user(session, user, language),
        'context': admin_serialize_context(session, context, language),
        'comments': rtip_dict['comments'],
        'messages': rtip_dict['messages'],
        'files': [],
        'submission_statuses': db_retrieve_all_submission_statuses(session, tid, language)
    }

    for rfile in session.query(models.ReceiverFile).filter(models.ReceiverFile.receivertip_id == rtip_id):
        rfile.last_access = datetime_now()
        rfile.downloads += 1
        file_dict = models.serializers.serialize_rfile(session, tid, rfile)
        file_dict['name'] = 'files/' + file_dict['name']
        file_dict['path'] = os.path.join(Settings.attachments_path, file_dict['filename'])
        file_dict['forged'] = False
        export_dict['files'].append(file_dict)

    for wf in session.query(models.WhistleblowerFile).filter(models.WhistleblowerFile.receivertip_id == models.ReceiverTip.id,
                                                             models.ReceiverTip.internaltip_id == rtip.internaltip_id,
                                                             models.InternalTip.id == rtip.internaltip_id):
        file_dict = models.serializers.serialize_wbfile(session, tid, wf)
        file_dict['name'] = 'files_from_recipients/' + file_dict['name']
        file_dict['path'] = os.path.join(Settings.attachments_path, file_dict['filename'])
        file_dict['forged'] = True  # To be removed as soon it will be encrypted
        export_dict['files'].append(file_dict)

    return export_dict


class ZipStreamProducer(object):
    """Streaming producter for ZipStream"""

    def __init__(self, handler, zipstreamObject):
        self.finish = Deferred()
        self.handler = handler
        self.zipstreamObject = zipstreamObject

    def start(self):
        self.handler.request.registerProducer(self, False)
        return self.finish

    def resumeProducing(self):
        if not self.handler:
            return

        data = self.zip_chunk()
        if data:
            self.handler.request.write(data)
        else:
            self.stopProducing()

    def stopProducing(self):
        self.handler.request.unregisterProducer()
        self.handler.request.finish()
        self.handler = None
        self.finish.callback(None)

    def zip_chunk(self):
        chunk = []
        chunk_size = 0

        for data in self.zipstreamObject:
            if data:
                chunk_size += len(data)
                chunk.append(data)
                if chunk_size >= abstract.FileDescriptor.bufferSize:
                    return b''.join(chunk)

        return b''.join(chunk)


class ExportHandler(BaseHandler):
    check_roles = 'receiver'
    handler_exec_time_threshold = 3600

    @inlineCallbacks
    def get(self, rtip_id):
        tip_export = yield get_tip_export(self.request.tid,
                                          self.current_user.user_id,
                                          rtip_id,
                                          self.request.language)

        if tip_export['crypto_tip_prv_key']:
            tip_export['tip'] = yield deferToThread(decrypt_tip, self.current_user.cc, tip_export['crypto_tip_prv_key'], tip_export['tip'])
            tip_export['comments'] = tip_export['tip']['comments']
            tip_export['messages'] = tip_export['tip']['messages']

            for file_dict in tip_export['files']:
                if file_dict['forged']:
                    continue

                tip_prv_key = GCE.asymmetric_decrypt(self.current_user.cc, tip_export['crypto_tip_prv_key'])
                file_dict['fo'] = GCE.streaming_encryption_open('DECRYPT', tip_prv_key, file_dict['path'])
                del file_dict['path']

        export_template = Templating().format_template(tip_export['notification']['export_template'], tip_export).encode()

        export_template = msdos_encode(export_template.decode()).encode()

        tip_export['files'].append({'fo': BytesIO(export_template), 'name': 'data.txt', 'forged': True})

        self.request.setHeader(b'X-Download-Options', b'noopen')
        self.request.setHeader(b'Content-Type', b'application/octet-stream')
        self.request.setHeader(b'Content-Disposition', b'attachment; filename="submission.zip"')

        self.zip_stream = iter(ZipStream(tip_export['files']))

        yield ZipStreamProducer(self, self.zip_stream).start()
