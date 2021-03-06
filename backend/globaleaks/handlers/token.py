# -*- coding: utf-8
#
# Handler implementing pre/post submission tokens for implementing rate limiting on whistleblower operations
from globaleaks.handlers.base import BaseHandler
from globaleaks.rest import errors, requests
from globaleaks.utils.ip import check_ip


class TokenCreate(BaseHandler):
    """
    This class implement the handler for requesting a token.
    """
    check_roles = 'none'

    def post(self):
        """
        This API create a Token, a temporary memory only object able to keep
        track of the submission. If the system is under stress, complete the
        submission will require some actions to be performed before the
        submission can be concluded (e.g. hashcash and captchas).
        """
        if not self.request.client_using_tor and not self.state.tenant_cache[self.request.tid]['https_whistleblower']:
            raise errors.TorNetworkRequired

        request = self.validate_message(self.request.content.read(), requests.TokenReqDesc)

        if (request['type'] == 'submission' and (not self.state.accept_submissions or
                                                 self.state.tenant_cache[self.request.tid]['disable_submissions'])) or \
            (self.state.tenant_cache[self.request.tid]['ip_filter_whistleblower_enable'] and
             not check_ip(self.state.tenant_cache[self.request.tid]['ip_filter_whistleblower'], self.request.client_ip)):
            raise errors.SubmissionDisabled

        token = self.state.tokens.new(self.request.tid, request['type'])

        if not self.request.client_using_tor and (self.request.client_proto == 'http' and
                                                  self.request.hostname not in ['127.0.0.1', 'localhost']):
            # Due to https://github.com/globaleaks/GlobaLeaks/issues/2088 the proof of work if currently
            # implemented only over Tor and HTTPS that are the production conditions.
            token.solved = True

        return token.serialize()


class TokenInstance(BaseHandler):
    """
    This class implements the handler for updating a token (e.g.: solving a captcha)
    """
    check_roles = 'none'

    def put(self, token_id):
        request = self.validate_message(self.request.content.read(), requests.TokenAnswerDesc)

        token = self.state.tokens.get(token_id)
        if token is None or self.request.tid != token.tid:
            raise errors.InvalidAuthentication

        token.update(request['answer'])

        return token.serialize()
