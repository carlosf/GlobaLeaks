# -*- coding: utf-8 -*-
#
# admin/lang
#  **************
#
# Backend supports for jQuery File Uploader, and implementation of the
# file language statically uploaded by the Admin

# This code differs from handlers/file.py because files here are not tracked in the DB
import json

from twisted.internet.defer import inlineCallbacks, returnValue

from globaleaks import models
from globaleaks.handlers.base import BaseHandler
from globaleaks.handlers.user import can_edit_general_settings_or_raise
from globaleaks.orm import transact


@transact
def get(session, tid, lang):
    texts = session.query(models.CustomTexts).filter(
        models.CustomTexts.tid == tid, models.CustomTexts.lang == lang).one_or_none()
    if texts is None:
        return {}

    return texts.texts


@transact
def update(session, tid, lang, request):
    texts = session.query(models.CustomTexts).filter(
        models.CustomTexts.tid == tid, models.CustomTexts.lang == lang).one_or_none()
    if texts is None:
        session.add(models.CustomTexts(
            {'tid': tid, 'lang': lang, 'texts': request}))
    else:
        texts.texts = request


class AdminL10NHandler(BaseHandler):
    check_roles = 'user'
    invalidate_cache = True

    @inlineCallbacks
    def get(self, lang):
        yield can_edit_general_settings_or_raise(self)
        result = yield get(self.request.tid, lang)
        returnValue(result)

    @inlineCallbacks
    def put(self, lang):
        yield can_edit_general_settings_or_raise(self)
        content = self.request.content.read()
        if isinstance(content, bytes):
            content = content.decode()

        result = yield update(self.request.tid, lang, json.loads(content))
        returnValue(result)

    @inlineCallbacks
    def delete(self, lang):
        yield can_edit_general_settings_or_raise(self)
        result = yield models.delete(models.CustomTexts, models.CustomTexts.tid == self.request.tid, models.CustomTexts.lang == lang)
        returnValue(result)
