import africastalking

from flask import current_app


def send_help_is_coming_sms(phone_number, incident_id):
    if not phone_number:
        raise ValueError("Incident does not have a phone number.")

    username = current_app.config.get(
        "AT_USERNAME",
        "sandbox"
    )

    api_key = current_app.config.get("AT_API_KEY")

    if not api_key:
        raise RuntimeError(
            "AT_API_KEY is missing from the application configuration."
        )

    africastalking.initialize(
        username,
        api_key
    )

    sms = africastalking.SMS

    message = (
        f"ResQ update for INC-{incident_id}: "
        "Help is coming. You will be contacted soon. "
        "Please keep your phone available."
    )

    return sms.send(
        message,
        [phone_number]
    )