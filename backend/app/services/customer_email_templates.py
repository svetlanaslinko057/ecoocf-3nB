"""
Premium transactional email templates for the BIBI Cars customer cabinet.

Everything here is plain string rendering — no Jinja, no external deps — so it
stays fast and dependency-free. Templates are written with email-client-safe
HTML: table-based layout, inline styles, web-safe fonts with graceful fallback,
and a dark + gold (#FEAE00) brand palette that matches the cabinet UI.

Public helpers:
    render_verification_email(code, name, ttl_minutes) -> (subject, html, text)
    render_welcome_email(name) -> (subject, html, text)
"""

from __future__ import annotations

from typing import Tuple

BRAND_GOLD = "#FEAE00"
BG_OUTER = "#0A0A09"
BG_CARD = "#1A1A18"
BG_INNER = "#0F0F0D"
BORDER = "#2C2C29"
TEXT = "#FFFFFF"
TEXT_MUTED = "#A7A7A1"

YEAR_FALLBACK = "2026"


def _shell(*, preheader: str, inner_html: str) -> str:
    """Wrap content in the shared responsive dark email shell."""
    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>BIBI Cars</title>
</head>
<body style="margin:0;padding:0;background:{BG_OUTER};">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;height:0;width:0;">
    {preheader}
  </div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{BG_OUTER};padding:32px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;width:100%;">
          <!-- Header / logo -->
          <tr>
            <td align="center" style="padding:8px 0 24px 0;">
              <span style="font-family:'Trebuchet MS',Helvetica,Arial,sans-serif;font-size:26px;font-weight:800;letter-spacing:2px;color:{TEXT};">
                BIBI<span style="color:{BRAND_GOLD};">CARS</span>
              </span>
            </td>
          </tr>
          <!-- Card -->
          <tr>
            <td style="background:{BG_CARD};border:1px solid {BORDER};border-radius:18px;padding:40px 36px;box-shadow:0 20px 60px rgba(0,0,0,0.55);">
              {inner_html}
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td align="center" style="padding:26px 16px 8px 16px;">
              <p style="margin:0 0 6px 0;font-family:Helvetica,Arial,sans-serif;font-size:12px;line-height:18px;color:{TEXT_MUTED};">
                You are receiving this email because an account was created with this address on BIBI Cars.
              </p>
              <p style="margin:0;font-family:Helvetica,Arial,sans-serif;font-size:12px;line-height:18px;color:#6A6A64;">
                &copy; {YEAR_FALLBACK} BIBI Cars &middot; Premium car import &amp; delivery
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def render_verification_email(code: str, name: str = "", ttl_minutes: int = 10) -> Tuple[str, str, str]:
    """Build the email-verification message.

    Returns (subject, html, text).
    """
    safe_name = (name or "").strip()
    greeting = f"Welcome, {safe_name}!" if safe_name else "Welcome to BIBI Cars!"
    digits = "".join(
        f"""<td align="center" style="padding:0 5px;">
              <div style="width:46px;height:60px;line-height:60px;background:{BG_OUTER};border:1px solid {BORDER};border-radius:10px;
                          font-family:'Courier New',monospace;font-size:30px;font-weight:700;color:{BRAND_GOLD};">{d}</div>
            </td>"""
        for d in str(code)
    )

    inner = f"""
      <p style="margin:0 0 6px 0;font-family:'Trebuchet MS',Helvetica,Arial,sans-serif;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:{BRAND_GOLD};font-weight:700;">
        Verify your email
      </p>
      <h1 style="margin:0 0 14px 0;font-family:'Trebuchet MS',Helvetica,Arial,sans-serif;font-size:28px;line-height:34px;color:{TEXT};font-weight:800;">
        {greeting}
      </h1>
      <p style="margin:0 0 28px 0;font-family:Helvetica,Arial,sans-serif;font-size:15px;line-height:24px;color:{TEXT_MUTED};">
        Thanks for joining BIBI Cars. To activate your personal cabinet and keep your account secure,
        enter the verification code below on the confirmation screen.
      </p>

      <!-- Code -->
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" style="margin:0 auto 26px auto;">
        <tr>{digits}</tr>
      </table>

      <p style="margin:0 0 28px 0;font-family:Helvetica,Arial,sans-serif;font-size:13px;line-height:20px;color:{TEXT_MUTED};text-align:center;">
        This code expires in <strong style="color:{TEXT};">{ttl_minutes} minutes</strong>.
      </p>

      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="background:{BG_INNER};border:1px solid {BORDER};border-radius:12px;padding:16px 18px;">
            <p style="margin:0;font-family:Helvetica,Arial,sans-serif;font-size:12.5px;line-height:19px;color:{TEXT_MUTED};">
              <strong style="color:{TEXT};">Didn't request this?</strong> You can safely ignore this email —
              no account will be activated without this code. Never share this code with anyone;
              BIBI Cars staff will never ask you for it.
            </p>
          </td>
        </tr>
      </table>
    """

    html = _shell(
        preheader=f"Your BIBI Cars verification code is {code}",
        inner_html=inner,
    )

    text = (
        f"{greeting}\n\n"
        f"Your BIBI Cars verification code is: {code}\n"
        f"This code expires in {ttl_minutes} minutes.\n\n"
        f"Enter it on the confirmation screen to activate your cabinet.\n\n"
        f"If you didn't create a BIBI Cars account, you can ignore this email.\n"
        f"Never share this code with anyone.\n\n"
        f"— BIBI Cars"
    )

    subject = f"{code} is your BIBI Cars verification code"
    return subject, html, text


def render_welcome_email(name: str = "") -> Tuple[str, str, str]:
    """Post-verification welcome email. Returns (subject, html, text)."""
    safe_name = (name or "").strip()
    greeting = f"You're all set, {safe_name}!" if safe_name else "You're all set!"

    inner = f"""
      <p style="margin:0 0 6px 0;font-family:'Trebuchet MS',Helvetica,Arial,sans-serif;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:{BRAND_GOLD};font-weight:700;">
        Account activated
      </p>
      <h1 style="margin:0 0 14px 0;font-family:'Trebuchet MS',Helvetica,Arial,sans-serif;font-size:28px;line-height:34px;color:{TEXT};font-weight:800;">
        {greeting}
      </h1>
      <p style="margin:0 0 24px 0;font-family:Helvetica,Arial,sans-serif;font-size:15px;line-height:24px;color:{TEXT_MUTED};">
        Your email has been verified and your BIBI Cars cabinet is ready. You can now track orders,
        manage documents, view invoices and follow every step of your car's journey — all in one place.
      </p>
    """

    html = _shell(
        preheader="Your BIBI Cars cabinet is ready.",
        inner_html=inner,
    )

    text = (
        f"{greeting}\n\n"
        f"Your email has been verified and your BIBI Cars cabinet is ready.\n"
        f"Sign in any time with your email and password.\n\n"
        f"— BIBI Cars"
    )

    subject = "Welcome to BIBI Cars — your cabinet is ready"
    return subject, html, text



def render_staff_login_otp_email(
    code: str,
    *,
    staff_email: str = "",
    staff_name: str = "",
    role: str = "team_lead",
    ttl_minutes: int = 10,
) -> Tuple[str, str, str]:
    """Login-approval OTP email for a team-lead sign-in.

    Sent to the configured administration inbox so the master-admin can approve
    the team-lead's first login of the session. Returns (subject, html, text).
    """
    who = (staff_name or "").strip() or (staff_email or "").strip() or "a team lead"
    role_label = (role or "team_lead").replace("_", " ").title()
    digits = "".join(
        f"""<td align="center" style="padding:0 5px;">
              <div style="width:46px;height:60px;line-height:60px;background:{BG_OUTER};border:1px solid {BORDER};border-radius:10px;
                          font-family:'Courier New',monospace;font-size:30px;font-weight:700;color:{BRAND_GOLD};">{d}</div>
            </td>"""
        for d in str(code)
    )

    inner = f"""
      <p style="margin:0 0 6px 0;font-family:'Trebuchet MS',Helvetica,Arial,sans-serif;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:{BRAND_GOLD};font-weight:700;">
        Login approval required
      </p>
      <h1 style="margin:0 0 14px 0;font-family:'Trebuchet MS',Helvetica,Arial,sans-serif;font-size:26px;line-height:32px;color:{TEXT};font-weight:800;">
        Team-lead sign-in
      </h1>
      <p style="margin:0 0 22px 0;font-family:Helvetica,Arial,sans-serif;font-size:15px;line-height:24px;color:{TEXT_MUTED};">
        <strong style="color:{TEXT};">{who}</strong> ({role_label}) is signing in to the BIBI Cars panel and needs
        a one-time approval code. Share the code below with them to complete the login.
      </p>

      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 22px 0;">
        <tr>
          <td style="background:{BG_INNER};border:1px solid {BORDER};border-radius:12px;padding:14px 18px;">
            <p style="margin:0;font-family:Helvetica,Arial,sans-serif;font-size:12.5px;line-height:20px;color:{TEXT_MUTED};">
              <span style="color:#6A6A64;">Account:</span> <strong style="color:{TEXT};">{staff_email or '—'}</strong><br/>
              <span style="color:#6A6A64;">Role:</span> <strong style="color:{TEXT};">{role_label}</strong>
            </p>
          </td>
        </tr>
      </table>

      <!-- Code -->
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" style="margin:0 auto 22px auto;">
        <tr>{digits}</tr>
      </table>

      <p style="margin:0 0 24px 0;font-family:Helvetica,Arial,sans-serif;font-size:13px;line-height:20px;color:{TEXT_MUTED};text-align:center;">
        This code expires in <strong style="color:{TEXT};">{ttl_minutes} minutes</strong>.
      </p>

      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="background:{BG_INNER};border:1px solid {BORDER};border-radius:12px;padding:16px 18px;">
            <p style="margin:0;font-family:Helvetica,Arial,sans-serif;font-size:12.5px;line-height:19px;color:{TEXT_MUTED};">
              <strong style="color:{TEXT};">Not expecting this?</strong> If you did not authorise this sign-in,
              do <strong style="color:{TEXT};">not</strong> share the code — the login cannot proceed without it.
              The same code is also visible in the admin panel under Security &middot; Pending logins.
            </p>
          </td>
        </tr>
      </table>
    """

    html = _shell(
        preheader=f"Team-lead login approval code: {code}",
        inner_html=inner,
    )

    text = (
        f"BIBI Cars — team-lead login approval\n\n"
        f"{who} ({role_label}) is signing in.\n"
        f"Account: {staff_email or '—'}\n\n"
        f"Approval code: {code}\n"
        f"Expires in {ttl_minutes} minutes.\n\n"
        f"Share this code with the team lead to complete the login.\n"
        f"If you did not authorise this sign-in, do not share the code.\n\n"
        f"— BIBI Cars"
    )

    subject = f"{code} — BIBI Cars team-lead login approval"
    return subject, html, text



def render_login_otp_email(code: str, name: str = "", ttl_minutes: int = 10) -> Tuple[str, str, str]:
    """Customer login one-time code (email-based 2FA on sign-in).

    Returns (subject, html, text).
    """
    safe_name = (name or "").strip()
    hello = f"Hi {safe_name}," if safe_name else "Hi,"
    digits = "".join(
        f"""<td align="center" style="padding:0 5px;">
              <div style="width:46px;height:60px;line-height:60px;background:{BG_OUTER};border:1px solid {BORDER};border-radius:10px;
                          font-family:'Courier New',monospace;font-size:30px;font-weight:700;color:{BRAND_GOLD};">{d}</div>
            </td>"""
        for d in str(code)
    )

    inner = f"""
      <p style="margin:0 0 6px 0;font-family:'Trebuchet MS',Helvetica,Arial,sans-serif;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:{BRAND_GOLD};font-weight:700;">
        Sign-in verification
      </p>
      <h1 style="margin:0 0 14px 0;font-family:'Trebuchet MS',Helvetica,Arial,sans-serif;font-size:26px;line-height:32px;color:{TEXT};font-weight:800;">
        Your login code
      </h1>
      <p style="margin:0 0 26px 0;font-family:Helvetica,Arial,sans-serif;font-size:15px;line-height:24px;color:{TEXT_MUTED};">
        {hello} a sign-in to your BIBI Cars cabinet needs a one-time code. Enter the code below
        on the verification screen to finish logging in.
      </p>

      <table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" style="margin:0 auto 26px auto;">
        <tr>{digits}</tr>
      </table>

      <p style="margin:0 0 26px 0;font-family:Helvetica,Arial,sans-serif;font-size:13px;line-height:20px;color:{TEXT_MUTED};text-align:center;">
        This code expires in <strong style="color:{TEXT};">{ttl_minutes} minutes</strong>.
      </p>

      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="background:{BG_INNER};border:1px solid {BORDER};border-radius:12px;padding:16px 18px;">
            <p style="margin:0;font-family:Helvetica,Arial,sans-serif;font-size:12.5px;line-height:19px;color:{TEXT_MUTED};">
              <strong style="color:{TEXT};">Didn't try to sign in?</strong> Someone may have your password.
              Do not share this code, and change your password from your cabinet as soon as possible.
            </p>
          </td>
        </tr>
      </table>
    """

    html = _shell(
        preheader=f"Your BIBI Cars login code is {code}",
        inner_html=inner,
    )
    text = (
        f"BIBI Cars — login verification\n\n"
        f"Your one-time login code: {code}\n"
        f"Expires in {ttl_minutes} minutes.\n\n"
        f"If you didn't try to sign in, do not share this code and change your password.\n\n"
        f"— BIBI Cars"
    )
    subject = f"{code} — BIBI Cars login code"
    return subject, html, text
