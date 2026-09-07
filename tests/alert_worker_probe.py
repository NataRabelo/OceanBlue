import os
from pathlib import Path
import sys

from scripts.test_environment import configure_test_environment


def main():
    configure_test_environment()
    from app import create_app
    from app.extensions import db
    from app.services.alerta_service import AlertaService
    from app.services.comunicacao_service import ComunicacaoService

    delivery_id, boundary, marker = sys.argv[1:]
    with create_app().app_context():
        commit = db.session.commit

        def claim():
            os._exit(73)

        def transport(**arguments):
            if boundary == "before_transport":
                os._exit(73)
            Path(marker).write_text("synthetic transport accepted", encoding="utf-8")
            os._exit(73)

        db.session.commit = claim if boundary == "claim" else commit
        ComunicacaoService.enviar = transport
        AlertaService.entregar(int(delivery_id), 1)


if __name__ == "__main__":
    main()
