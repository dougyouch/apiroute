import email
import email.policy


def parse_multipart(content: bytes, content_type: str) -> list[tuple[str, str | None, str, bytes]]:
    """The parts of a multipart/form-data body, in order: (name, filename, type, content)."""
    message = email.message_from_bytes(
        f"Content-Type: {content_type}\r\n\r\n".encode() + content, policy=email.policy.HTTP
    )
    return [
        (
            part.get_param("name", header="content-disposition"),
            part.get_filename(),
            part.get_content_type(),
            part.get_payload(decode=True),
        )
        for part in message.iter_parts()
    ]
