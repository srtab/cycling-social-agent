"""Telegram approval bot.

Exposes:
- ``send_draft_card``: posts a draft preview to the rider's chat with action buttons.
- ``handle_callback`` / ``handle_text``: handlers for button presses and follow-up
  text replies (edit text, regenerate hint, reschedule time).

The bot writes user actions to the DB. The agent loop reads them on the next
cycle. There is no in-memory waiting between bot and agent.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import dateparser
import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from cycling_agent.db.models import DraftStatus
from cycling_agent.db.repo import Repository

log = structlog.get_logger(__name__)

# Callback data prefixes (kept short — Telegram limits callback_data to 64 bytes).
CB_APPROVE_QUEUED = "aq"
CB_APPROVE_NOW = "an"
CB_EDIT = "ed"
CB_REGENERATE = "rg"
CB_REJECT = "rj"
CB_RESCHEDULE = "rs"


def callback_data(action: str, *, draft_id: int) -> str:
    return f"{action}:{draft_id}"


class ApprovalBot:
    """Stateless wrapper over python-telegram-bot for the cycling agent."""

    def __init__(
        self,
        *,
        repo: Repository,
        chat_id: int,
        telegram_bot: Any | None = None,
    ) -> None:
        self._repo = repo
        self._chat_id = chat_id
        self._bot = telegram_bot  # set by register_handlers when running in app

    # --- public API -----------------------------------------------------------

    def register_handlers(self, application: Application) -> None:
        """Wire handlers into a python-telegram-bot Application."""
        self._bot = application.bot
        application.add_handler(CommandHandler("start", self._handle_start))
        application.add_handler(CallbackQueryHandler(self.handle_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))

    async def send_draft_card(
        self,
        *,
        draft_id: int,
        caption: str,
        media_paths: Sequence[Path],
    ) -> int:
        """Post a draft preview to the rider's chat, return the telegram message id."""
        if self._bot is None:
            raise RuntimeError("ApprovalBot.send_draft_card requires a telegram bot")

        markup = self._build_keyboard(draft_id, include_reschedule=False)
        media = next((p for p in media_paths if p.exists()), None)
        if media is None:
            sent = await self._bot.send_message(
                chat_id=self._chat_id, text=caption, reply_markup=markup
            )
        else:
            with media.open("rb") as fh:
                sent = await self._bot.send_photo(
                    chat_id=self._chat_id, photo=fh, caption=caption, reply_markup=markup
                )
        return int(sent.message_id)

    # --- handlers -------------------------------------------------------------

    async def _handle_start(
        self, update: Any, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        await update.message.reply_text("cycling-agent ready. I'll send you race posts to approve.")

    async def handle_callback(
        self, update: Any, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        chat_id = getattr(update.effective_chat, "id", None)
        if chat_id != self._chat_id:
            log.warning("approval.bot.foreign_chat", chat_id=chat_id)
            return

        query = update.callback_query
        try:
            action, draft_id = self._parse_callback(query.data)
        except ValueError:
            await query.answer("bad callback")
            return

        await query.answer()  # acknowledges to Telegram immediately

        if action == CB_APPROVE_QUEUED:
            self._repo.set_approved(draft_id, post_now=False)
            self._repo.log_approval_event(
                draft_id=draft_id, event="approved",
                payload=json.dumps({"post_now": False}),
            )
            await context.bot.send_message(
                chat_id=self._chat_id,
                text=f"Draft #{draft_id} approved — queued for next publish window.",
            )

        elif action == CB_APPROVE_NOW:
            self._repo.set_approved(draft_id, post_now=True)
            self._repo.log_approval_event(
                draft_id=draft_id, event="approved",
                payload=json.dumps({"post_now": True}),
            )
            await context.bot.send_message(
                chat_id=self._chat_id, text=f"Draft #{draft_id} approved — posting now.",
            )

        elif action == CB_REJECT:
            self._repo.set_draft_status(draft_id, DraftStatus.REJECTED)
            self._repo.log_approval_event(draft_id=draft_id, event="rejected", payload="{}")
            await context.bot.send_message(
                chat_id=self._chat_id, text=f"Draft #{draft_id} rejected.",
            )

        elif action == CB_REGENERATE:
            self._repo.set_draft_status(draft_id, DraftStatus.REGENERATING)
            context.user_data["awaiting_hint_for"] = draft_id
            await context.bot.send_message(
                chat_id=self._chat_id,
                text=(
                    f"Send an optional hint for the regenerated draft #{draft_id} "
                    f"(e.g. 'more grateful, less hype'). Send 'skip' to regenerate without a hint."
                ),
            )

        elif action == CB_EDIT:
            self._repo.set_draft_status(draft_id, DraftStatus.EDITING)
            context.user_data["awaiting_edit_for"] = draft_id
            await context.bot.send_message(
                chat_id=self._chat_id,
                text=f"Send the replacement caption for draft #{draft_id}.",
            )

        elif action == CB_RESCHEDULE:
            context.user_data["awaiting_reschedule_for"] = draft_id
            await context.bot.send_message(
                chat_id=self._chat_id,
                text=(
                    f"Send a new time for draft #{draft_id} "
                    f"(e.g. '2026-04-02 21:00' or 'tomorrow 19:00')."
                ),
            )

    async def handle_text(
        self, update: Any, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        chat_id = getattr(update.effective_chat, "id", None)
        if chat_id != self._chat_id:
            return

        text = (update.message.text or "").strip()

        edit_for = context.user_data.pop("awaiting_edit_for", None)
        if edit_for is not None:
            self._repo.set_draft_status(
                int(edit_for), DraftStatus.AWAITING_APPROVAL, caption=text
            )
            self._repo.log_approval_event(
                draft_id=int(edit_for), event="edited",
                payload=json.dumps({"new_caption": text}),
            )
            await update.message.reply_text(f"Draft #{edit_for} updated. Tap Approve to publish.")
            return

        hint_for = context.user_data.pop("awaiting_hint_for", None)
        if hint_for is not None:
            hint = "" if text.lower() == "skip" else text
            self._repo.set_draft_status(int(hint_for), DraftStatus.REGENERATING, feedback_hint=hint)
            self._repo.log_approval_event(
                draft_id=int(hint_for), event="regenerated",
                payload=json.dumps({"hint": hint}),
            )
            await update.message.reply_text(
                f"Hint recorded for draft #{hint_for}. Will regenerate on next cycle."
            )
            return

        resched_for = context.user_data.pop("awaiting_reschedule_for", None)
        if resched_for is not None:
            parsed = dateparser.parse(text, settings={"PREFER_DATES_FROM": "future"})
            if parsed is None:
                await update.message.reply_text(
                    f"Could not parse '{text}' as a date. Try '2026-04-02 21:00'."
                )
                context.user_data["awaiting_reschedule_for"] = resched_for
                return
            self._repo.reschedule_draft(int(resched_for), parsed)
            self._repo.log_approval_event(
                draft_id=int(resched_for), event="rescheduled",
                payload=json.dumps({"scheduled_for": parsed.isoformat()}),
            )
            await update.message.reply_text(
                f"Draft #{resched_for} rescheduled to {parsed.isoformat(timespec='minutes')}."
            )
            return

    async def handle_photo(
        self, update: Any, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        await update.message.reply_text(
            "Photo received — attaching photos to drafts will be supported in a follow-up."
        )

    # --- helpers --------------------------------------------------------------

    def _parse_callback(self, data: str) -> tuple[str, int]:
        action, _, draft_id_str = data.partition(":")
        if not action or not draft_id_str:
            raise ValueError(f"bad callback data: {data!r}")
        return action, int(draft_id_str)

    def _build_keyboard(
        self, draft_id: int, *, include_reschedule: bool
    ) -> InlineKeyboardMarkup:
        rows = [
            [
                InlineKeyboardButton(
                    "Approve (queued)",
                    callback_data=callback_data(CB_APPROVE_QUEUED, draft_id=draft_id),
                ),
                InlineKeyboardButton(
                    "Approve & post now",
                    callback_data=callback_data(CB_APPROVE_NOW, draft_id=draft_id),
                ),
            ],
            [
                InlineKeyboardButton("Edit", callback_data=callback_data(CB_EDIT, draft_id=draft_id)),
                InlineKeyboardButton("Regenerate", callback_data=callback_data(CB_REGENERATE, draft_id=draft_id)),
                InlineKeyboardButton("Reject", callback_data=callback_data(CB_REJECT, draft_id=draft_id)),
            ],
        ]
        if include_reschedule:
            rows.append(
                [
                    InlineKeyboardButton(
                        "Reschedule",
                        callback_data=callback_data(CB_RESCHEDULE, draft_id=draft_id),
                    )
                ]
            )
        return InlineKeyboardMarkup(rows)
