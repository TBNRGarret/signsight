"""Authorize staff HTML as well as its API; public assets remain available."""
import os
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from backend.app.core.security import get_current_session, get_current_user, oauth2_scheme


class WebFiles(StaticFiles):
    def is_staff_document(self, path):
        full_path, stat_result = self.lookup_path(path)
        # Filesystem identity also catches Windows case/short-name aliases.
        return bool(stat_result and os.path.samefile(full_path, Path(self.directory) / 'management.html'))

    async def get_response(self, path, scope):
        if await run_in_threadpool(self.is_staff_document, path):
            request = Request(scope)
            token = await oauth2_scheme(request)

            def check_access():
                with request.app.state.session_factory() as db:
                    try:
                        session = get_current_session(request, token, db)
                        user = get_current_user(session, db)
                    except HTTPException as error:
                        if error.status_code in (401, 403):
                            return 'login'
                        raise
                    return None if user.role in ('manager', 'admin') else 'forbidden'

            denied = await run_in_threadpool(check_access)
            if denied:
                return RedirectResponse('/web/index.html?staff=' + denied, status_code=303,
                                        headers={'Cache-Control': 'no-store'})
            response = await super().get_response(path, scope)
            response.headers['Cache-Control'] = 'no-store'
            return response
        return await super().get_response(path, scope)
