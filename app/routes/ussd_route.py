from flask import Blueprint, request, Response

from app.channels.ussd import USSDHandler


ussd_bp = Blueprint(
    "ussd",
    __name__
)


@ussd_bp.route("/ussd", methods=["GET", "POST"])
def ussd_callback():
    session_id = request.values.get(
        "sessionId",
        ""
    )

    phone_number = request.values.get(
        "phoneNumber",
        ""
    )

    text = request.values.get(
        "text",
        ""
    )

    network = request.values.get(
        "networkCode",
        ""
    )

    response_text, is_end = USSDHandler.handle_request(
        session_id=session_id,
        phone_number=phone_number,
        text=text,
        network=network
    )

    prefix = "END" if is_end else "CON"

    return Response(
        f"{prefix} {response_text}",
        status=200,
        mimetype="text/plain"
    )