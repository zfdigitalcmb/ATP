import requests

def send_email_via_functionapp(email_subject, email_body, recipients,image_path=None):
    url = "https://zfcmbatpemail-gcgpgrdrhqgcagbb.southeastasia-01.azurewebsites.net/api/send_email?code=83VjgyEIB3NHVU0xzF6xofBCipfWYgFWVvPIXrOrfomMAzFurezp1w=="

    payload = {
        "subject": email_subject,
        "body": email_body,
        "recipients": recipients,
        "image_path": image_path  # optional
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            return "Email sent successfully via Function App"
        else:
            return f"Failed: {response.text}"
    except Exception as e:
        return f"Error calling Function App: {e}"