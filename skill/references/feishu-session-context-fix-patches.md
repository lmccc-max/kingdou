# Feishu Gateway Session Context Fix — Code Patches

This reference documents the exact code changes applied to fix:
1. Session context (`chat_id`) not injected into AI system prompt
2. User ID isolation failure (`user_id: None`)

## Patch 1: Session context injection (gateway/run.py lines 12516-12542)

```python
            # Inject session context (chat_id, chat_name, user_id, user_name) into system prompt
            # This ensures AI can access current conversation's context for multi-group support
            try:
                from gateway.session_context import get_session_env
                session_chat_id = get_session_env("HERMES_SESSION_CHAT_ID", "")
                session_chat_name = get_session_env("HERMES_SESSION_CHAT_NAME", "")
                session_user_id = get_session_env("HERMES_SESSION_USER_ID", "")
                session_user_name = get_session_env("HERMES_SESSION_USER_NAME", "")
                session_platform = get_session_env("HERMES_SESSION_PLATFORM", "")
                
                # DEBUG: Log session context injection
                logger.info(f"[SESSION_CONTEXT] chat_id={session_chat_id}, chat_name={session_chat_name}, user_id={session_user_id}, platform={session_platform}")

                if session_chat_id:
                    session_context_info = [
                        "",
                        "<!-- Session Context -->",
                        f"[Current Conversation ID: {session_chat_id}]",
                    ]
                    if session_chat_name:
                        session_context_info.append(f"[Current Conversation Name: {session_chat_name}]")
                    if session_user_id or session_user_name:
                        session_context_info.append(f"[Current User: {session_user_name or session_user_id}]")
                    if session_platform:
                        session_context_info.append(f"[Current Platform: {session_platform}]")

                    combined_ephemeral = (combined_ephemeral + "\n\n" + "\n".join(session_context_info)).strip()
            except Exception:
                pass  # Non-gateway context (CLI/cron) won't have session vars
```

## Patch 2: _resolve_sender_profile fallback (gateway/platforms/feishu.py lines 3546-3553)

```python
        # Fallback: if all IDs are None (e.g. malformed events), use a
        # deterministic placeholder so session isolation still works.
        if not primary_id:
            primary_id = f"anon-{hash(str(sender_id)) & 0xFFFFFFFF:08x}"
            logger.warning(
                "[Feishu] No user_id or open_id found for sender %r; using fallback %s",
                sender_id, primary_id,
            )
```

## Patch 3: build_session_key fallback (gateway/session.py lines 658-671)

```python
    elif isolate_user and not participant_id:
        # user_id and user_id_alt are both None despite per-user isolation
        # being enabled.  Use a deterministic fallback derived from other
        # context so the session is still scoped (prevents cross-user
        # context pollution in edge cases like Feishu card actions).
        fallback = f"anon-session-{hash(key_parts[-1]) & 0xFFFFFFFF:08x}" if key_parts else "anon-session"
        key_parts.append(fallback)
        import logging
        _logger = logging.getLogger("gateway.session")
        _logger.warning(
            "build_session_key: user_id and user_id_alt both None for %s group session; "
            "using fallback %s (chat_id=%s)",
            source.platform.value, fallback, source.chat_id,
        )
```

## Patch 4: Debug tracing (gateway/platforms/feishu.py lines 2789-2795)

```python
        # Trace: log when user_id is None (session isolation debug)
        if not sender_profile.get("user_id"):
            logger.warning(
                "[Feishu] sender_profile user_id is None! chat_id=%s sender_id=%r profile=%r", 
                chat_id, sender_id, sender_profile,
            )
```

## Verification Commands

```bash
# Check session context injection
grep -i "SESSION_CONTEXT" ~/.hermes/logs/gateway.log | tail -5

# Check for user_id=None warnings
grep -i "user_id is None\|user_id_alt.*None" ~/.hermes/logs/gateway.log | tail -10

# Restart gateway after code changes
# Send /restart in the gateway chat
```