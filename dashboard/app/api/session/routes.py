import base64
import socket

from io import BytesIO
from http import HTTPStatus as status

from flask import current_app, jsonify, request, send_file
from flask_jwt_extended import jwt_required

from app.api.session import bp
from app.extensions import db
from app.models.session import Session
from app.models.session_html import SessionHtml
from app.telemetry.psst import dataclass_from_dict


@bp.route('', methods=['GET'])
def get_all():
    entities = db.session.execute(db.select(Session)).scalars()
    return jsonify(list(entities)), status.OK


@bp.route('/<int:id>/psst', methods=['GET'])
def get_psst(id: int):
    entity = db.session.execute(
        db.select(Session).filter_by(id=id)).scalar_one_or_none()
    if not entity:
        return jsonify(msg="Session does not exist!"), status.NOT_FOUND
    data = BytesIO(entity.data)
    return send_file(
        data,
        as_attachment=True,
        download_name=f"{entity.name}.psst",
        mimetype="application/octet-stream",
    )


@bp.route('/<int:id>', methods=['GET'])
def get(id: int):
    entity = db.session.execute(
        db.select(Session).filter_by(id=id)).scalar_one_or_none()
    if not entity:
        return jsonify(msg="Session does not exist!"), status.NOT_FOUND
    return jsonify(entity), status.OK


@bp.route('/<int:id>', methods=['DELETE'])
@jwt_required()
def delete(id: int):
    db.session.execute(db.delete(Session).filter_by(id=id))
    db.session.execute(db.delete(SessionHtml).filter_by(id=id))
    db.session.commit()
    return '', status.NO_CONTENT


@bp.route('', methods=['PUT'])
@jwt_required()
def put():
    try:
        data = request.json
        name = bytes(data['name'], 'ascii')
        setup_id = int(data['setup'])
        encoded_sst = data['data']
        sst_data = base64.b64decode(encoded_sst)
    except BaseException:
        return jsonify(msg="Invalid data for Session"), status.BAD_REQUEST

    gosst_server = (current_app.config['GOSST_HOST'],
                    current_app.config['GOSST_PORT'])
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(gosst_server)

    # We don't have a board ID here, so we use the setup ID prefixed with
    # "SETUP_". This is handled in gosst-tcp.
    header = (b'SETUP_' + int.to_bytes(setup_id, 4, 'little') +
              len(sst_data).to_bytes(8, 'little', signed=False) +
              name)
    client_socket.send(header)

    # wait for header response
    response = client_socket.recv(1)[0]
    if response != 4:
        return jsonify(msg="Header was not accepted"), status.BAD_REQUEST

    # send SST data
    client_socket.send(sst_data)
    response = client_socket.recv(1)[0]
    if response != 6:
        return jsonify(msg="Session could not be imported"), status.BAD_REQUEST

    response = client_socket.recv(4)
    id = int.from_bytes(response, 'little')

    if 'desc' in data:
        db.session.execute(db.update(Session).filter_by(id=id).values(
            description=data['desc']
        ))
        db.session.commit()

    client_socket.close()
    return jsonify(id=id), status.CREATED


@bp.route('/psst', methods=['PUT'])
@jwt_required()
def put_processed():
    session_dict = request.json
    session_data = session_dict.pop('data')
    entity = dataclass_from_dict(Session, session_dict)
    if not entity or not entity.validate():
        return jsonify(msg="Invalid data for Session"), status.BAD_REQUEST
    entity.psst = session_data
    entity = db.session.merge(entity)
    db.session.commit()
    return jsonify(id=entity.id), status.CREATED


@bp.route('/<int:id>', methods=['PATCH'])
@jwt_required()
def patch(id: int):
    data = request.json
    db.session.execute(db.update(Session).filter_by(id=id).values(
        name=data['name'],
        description=data['desc']
    ))
    db.session.commit()
    return '', status.NO_CONTENT
