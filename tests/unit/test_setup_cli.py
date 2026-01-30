"""Tests for setup CLI."""

import pytest
import asyncio
import gc
import time
from unittest.mock import AsyncMock, patch, MagicMock
import typer

from src.models.agent_models import AgentResponse
from src.models.scraper_models import ScrapeResult
from src.cli.setup_cli import (
    setup,
    test as cli_test_command,
    _prompt_with_help,
    _prompt_with_validation,
    _run_test_repl,
    _show_facebook_credential_help,
    _validate_page_id,
    _validate_page_access_token,
    _validate_verify_token,
    ACTION_CONTINUE,
    ACTION_EXIT,
    ACTION_TEST_BOT,
)

# Valid Facebook credentials for tests (must pass validation in setup flow)
VALID_PAGE_ID = "123456789012345"
VALID_PAGE_ACCESS_TOKEN = "EAAA" + "x" * 100  # EAAA + 100 chars = 104 total
VALID_VERIFY_TOKEN = "verify-token-12"


class TestSetupCLI:
    """Test setup CLI command."""

    def setup_method(self, method):
        """Ensure clean state before each test."""
        # Clear any existing event loop
        try:
            asyncio.set_event_loop(None)
        except Exception:
            pass

    def teardown_method(self, method):
        """Clean up event loops and async resources after each test to prevent resource warnings."""
        # First: Close any mock HTTP clients that might have open sockets
        try:
            # Check for any mock HTTP clients from CopilotService or Supabase mocks
            # These are created via @patch decorators, so they're in the test method's locals
            # We'll clean them up by ensuring their async context managers are properly closed
            for attr_name in dir(self):
                if "mock" in attr_name.lower():
                    try:
                        mock_obj = getattr(self, attr_name, None)
                        if mock_obj is not None and hasattr(mock_obj, "reset_mock"):
                            # Reset the mock to clear any state
                            mock_obj.reset_mock()
                            # If it's an async context manager mock, ensure __aexit__ is called
                            if hasattr(mock_obj, "__aenter__") and hasattr(
                                mock_obj, "__aexit__"
                            ):
                                try:
                                    # Simulate proper async context manager cleanup
                                    if hasattr(mock_obj.__aexit__, "return_value"):
                                        mock_obj.__aexit__.return_value = None
                                except Exception:
                                    pass
                    except Exception:
                        pass
        except Exception:
            pass

        # Enhanced cleanup with better error handling
        try:
            # Try to get running loop first
            try:
                loop = asyncio.get_running_loop()
                # If we have a running loop, we can't close it from here
                return
            except RuntimeError:
                loop = None

            # If no running loop, try to get the event loop
            if loop is None:
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = None

            # Clean up the loop if it exists and is not closed
            if loop is not None and not loop.is_closed():
                # Check if loop is running - if so, we can't close it
                if loop.is_running():
                    return

                try:
                    # Cancel all pending tasks
                    tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
                    for t in tasks:
                        t.cancel()
                    if tasks:
                        loop.run_until_complete(
                            asyncio.gather(*tasks, return_exceptions=True)
                        )
                    # Shutdown async generators to close any open resources (sockets, etc.)
                    loop.run_until_complete(loop.shutdown_asyncgens())
                    loop.close()
                except (RuntimeError, Exception):
                    # Ignore errors during cleanup
                    pass
        except Exception:
            # Ignore any errors during cleanup
            pass
        finally:
            # Always clear the event loop reference
            try:
                asyncio.set_event_loop(None)
            except Exception:
                pass
            # Add a small delay to allow async cleanup to complete before garbage collection
            # This helps ensure that async generators and context managers have time to close
            time.sleep(0.01)  # 10ms delay to allow async cleanup
            # Use gc.collect() defensively, but suppress ResourceWarnings during collection
            # as they may come from mocked resources that don't need real cleanup
            import warnings

            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=ResourceWarning)
                for _ in range(3):
                    gc.collect()
                    time.sleep(0.002)  # Small delay between collection passes

    @patch("src.cli.setup_cli.create_bot_configuration")
    @patch("src.cli.setup_cli.create_reference_document")
    @patch("src.cli.setup_cli.build_reference_document")
    @patch("src.cli.setup_cli.scrape_website")
    @patch("src.cli.setup_cli.get_reference_document_by_source_url")
    @patch("src.config.get_settings")
    @patch("src.db.client.get_supabase_client")
    @patch("src.cli.setup_cli.questionary.select")
    @patch("src.cli.setup_cli.typer.confirm")
    @patch("src.cli.setup_cli.typer.prompt")
    @patch("src.cli.setup_cli.typer.echo")
    def test_setup_complete_flow(
        self,
        mock_echo,
        mock_prompt,
        mock_confirm,
        mock_questionary_select,
        mock_get_supabase,
        mock_get_settings,
        mock_get_ref_doc,
        mock_scrape,
        mock_build_ref,
        mock_create_ref_doc,
        mock_create_bot,
    ):
        """Test complete setup flow (no existing reference doc)."""
        mock_get_ref_doc.return_value = None  # No existing doc; full scrape/build/store
        mock_confirm.return_value = True
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.copilot_cli_host = "http://localhost:5909"
        mock_settings.copilot_enabled = True
        mock_get_settings.return_value = mock_settings

        # Mock Supabase
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        # Mock scraping (ScrapeResult with empty pages so indexing step does nothing)
        mock_scrape.return_value = ScrapeResult(
            pages=[], chunks=["chunk1", "chunk2", "chunk3"], content_hash="hash"
        )

        # Mock reference doc building (returns markdown string, not tuple)
        mock_build_ref.return_value = "# Reference Document"

        # Mock database operations
        mock_create_ref_doc.return_value = "doc-123"
        mock_create_bot.return_value = MagicMock()

        # Action menu: Continue; then tone: Professional
        mock_questionary_select.return_value.ask.side_effect = [
            ACTION_CONTINUE,
            "Professional",
        ]

        # Mock typer prompts: website, then Facebook credentials (must pass validation)
        mock_prompt.side_effect = [
            "https://example.com",  # website_url
            VALID_PAGE_ID,
            VALID_PAGE_ACCESS_TOKEN,
            VALID_VERIFY_TOKEN,
        ]

        # Run setup
        setup()

        # Verify lookup for existing doc
        mock_get_ref_doc.assert_called_once_with("https://example.com")

        # Verify scraping was called with normalized URL
        mock_scrape.assert_called_once_with("https://example.com")

        # Verify reference doc was built
        mock_build_ref.assert_called_once()

        # Verify database operations
        mock_create_ref_doc.assert_called_once()
        mock_create_bot.assert_called_once()

    @patch("src.cli.setup_cli.get_reference_document_by_source_url")
    @patch("src.config.get_settings")
    @patch("src.db.client.get_supabase_client")
    @patch("src.cli.setup_cli.typer.prompt")
    @patch("src.cli.setup_cli.typer.echo")
    @patch("src.cli.setup_cli.scrape_website")
    def test_setup_scraping_error(
        self,
        mock_scrape,
        mock_echo,
        mock_prompt,
        mock_get_supabase,
        mock_get_settings,
        mock_get_ref_doc,
    ):
        """Test error handling when scraping fails."""
        mock_get_ref_doc.return_value = None
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.copilot_cli_host = "http://localhost:5909"
        mock_settings.copilot_enabled = True
        mock_get_settings.return_value = mock_settings

        mock_prompt.return_value = "https://example.com"
        mock_scrape.side_effect = Exception("Scraping failed")

        with pytest.raises(typer.Exit):
            setup()

        # Verify error was echoed
        error_calls = [
            call for call in mock_echo.call_args_list if "Error" in str(call)
        ]
        assert len(error_calls) > 0

    @patch("src.cli.setup_cli.get_reference_document_by_source_url")
    @patch("src.config.get_settings")
    @patch("src.db.client.get_supabase_client")
    @patch("src.cli.setup_cli.typer.prompt")
    @patch("src.cli.setup_cli.typer.echo")
    @patch("src.cli.setup_cli.scrape_website")
    @patch("src.cli.setup_cli.build_reference_document")
    def test_setup_reference_doc_error(
        self,
        mock_build_ref,
        mock_scrape,
        mock_echo,
        mock_prompt,
        mock_get_supabase,
        mock_get_settings,
        mock_get_ref_doc,
    ):
        """Test error handling when reference doc generation fails."""
        mock_get_ref_doc.return_value = None
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.copilot_cli_host = "http://localhost:5909"
        mock_settings.copilot_enabled = True
        mock_get_settings.return_value = mock_settings

        mock_prompt.return_value = "https://example.com"
        mock_scrape.return_value = ScrapeResult(pages=[], chunks=["chunk1"], content_hash="h")
        mock_build_ref.side_effect = Exception("Reference doc generation failed")

        with pytest.raises(typer.Exit):
            setup()

        # Verify error was echoed
        error_calls = [
            call for call in mock_echo.call_args_list if "Error" in str(call)
        ]
        assert len(error_calls) > 0

    @patch("src.cli.setup_cli.get_reference_document_by_source_url")
    @patch("src.config.get_settings")
    @patch("src.db.client.get_supabase_client")
    @patch("src.cli.setup_cli.typer.prompt")
    @patch("src.cli.setup_cli.typer.echo")
    @patch("src.cli.setup_cli.scrape_website")
    @patch("src.cli.setup_cli.build_reference_document")
    @patch("src.cli.setup_cli.create_reference_document")
    def test_setup_database_error(
        self,
        mock_create_ref_doc,
        mock_build_ref,
        mock_scrape,
        mock_echo,
        mock_prompt,
        mock_get_supabase,
        mock_get_settings,
        mock_get_ref_doc,
    ):
        """Test error handling when database operations fail."""
        mock_get_ref_doc.return_value = None
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.copilot_cli_host = "http://localhost:5909"
        mock_settings.copilot_enabled = True
        mock_get_settings.return_value = mock_settings

        # Provide enough prompt values for all prompts until the database error
        mock_prompt.side_effect = [
            "https://example.com",  # website_url
            "Professional",  # tone
            "page-123",  # page_id (never reached due to error)
            "token-123",
            "verify-123",
        ]
        mock_scrape.return_value = ScrapeResult(pages=[], chunks=["chunk1"], content_hash="h")
        mock_build_ref.return_value = "# Doc"
        mock_create_ref_doc.side_effect = Exception("Database error")

        with pytest.raises(typer.Exit):
            setup()

        # Verify error was echoed
        error_calls = [
            call for call in mock_echo.call_args_list if "Error" in str(call)
        ]
        assert len(error_calls) > 0

    @patch("src.cli.setup_cli.create_bot_configuration")
    @patch("src.cli.setup_cli.create_reference_document")
    @patch("src.cli.setup_cli.build_reference_document")
    @patch("src.cli.setup_cli.scrape_website")
    @patch("src.cli.setup_cli.get_reference_document_by_source_url")
    @patch("src.config.get_settings")
    @patch("src.db.client.get_supabase_client")
    @patch("src.cli.setup_cli.questionary.select")
    @patch("src.cli.setup_cli.typer.confirm")
    @patch("src.cli.setup_cli.typer.prompt")
    @patch("src.cli.setup_cli.typer.echo")
    def test_setup_tone_selection(
        self,
        mock_echo,
        mock_prompt,
        mock_confirm,
        mock_questionary_select,
        mock_get_supabase,
        mock_get_settings,
        mock_get_ref_doc,
        mock_scrape,
        mock_build_ref,
        mock_create_ref_doc,
        mock_create_bot,
    ):
        """Test tone selection step (arrow-key select)."""
        mock_get_ref_doc.return_value = None
        mock_confirm.return_value = True
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.copilot_cli_host = "http://localhost:5909"
        mock_settings.copilot_enabled = True
        mock_get_settings.return_value = mock_settings

        mock_questionary_select.return_value.ask.side_effect = [
            ACTION_CONTINUE,
            "Professional",
        ]
        mock_prompt.side_effect = [
            "https://example.com",
            VALID_PAGE_ID,
            VALID_PAGE_ACCESS_TOKEN,
            VALID_VERIFY_TOKEN,
        ]
        mock_scrape.return_value = ScrapeResult(pages=[], chunks=["chunk1"], content_hash="h")
        mock_build_ref.return_value = "# Doc"
        mock_create_ref_doc.return_value = "doc-123"
        mock_create_bot.return_value = MagicMock()

        setup()

        # Verify tone was used in bot configuration
        bot_call = mock_create_bot.call_args
        assert bot_call[1]["tone"] == "Professional"

    @patch("src.cli.setup_cli.create_bot_configuration")
    @patch("src.cli.setup_cli.create_reference_document")
    @patch("src.cli.setup_cli.build_reference_document")
    @patch("src.cli.setup_cli.scrape_website")
    @patch("src.cli.setup_cli.get_reference_document_by_source_url")
    @patch("src.config.get_settings")
    @patch("src.db.client.get_supabase_client")
    @patch("src.cli.setup_cli.questionary.select")
    @patch("src.cli.setup_cli.typer.confirm")
    @patch("src.cli.setup_cli.typer.prompt")
    @patch("src.cli.setup_cli.typer.echo")
    def test_setup_prints_webhook_url(
        self,
        mock_echo,
        mock_prompt,
        mock_confirm,
        mock_questionary_select,
        mock_get_supabase,
        mock_get_settings,
        mock_get_ref_doc,
        mock_scrape,
        mock_build_ref,
        mock_create_ref_doc,
        mock_create_bot,
    ):
        """Test that setup prints webhook URL and next steps."""
        mock_get_ref_doc.return_value = None
        mock_confirm.return_value = True
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.copilot_cli_host = "http://localhost:5909"
        mock_settings.copilot_enabled = True
        mock_get_settings.return_value = mock_settings

        mock_questionary_select.return_value.ask.side_effect = [
            ACTION_CONTINUE,
            "Professional",
        ]
        mock_prompt.side_effect = [
            "https://example.com",
            VALID_PAGE_ID,
            VALID_PAGE_ACCESS_TOKEN,
            VALID_VERIFY_TOKEN,
        ]
        mock_scrape.return_value = ScrapeResult(pages=[], chunks=["chunk1"], content_hash="h")
        mock_build_ref.return_value = "# Doc"
        mock_create_ref_doc.return_value = "doc-123"
        mock_create_bot.return_value = MagicMock()

        setup()

        # Verify webhook URL and next steps were printed
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        webhook_mentions = [call for call in echo_calls if "webhook" in call.lower()]
        assert len(webhook_mentions) > 0

    @patch("src.cli.setup_cli.get_scraped_pages_by_reference_doc")
    @patch("src.cli.setup_cli.create_bot_configuration")
    @patch("src.cli.setup_cli.create_reference_document")
    @patch("src.cli.setup_cli.build_reference_document")
    @patch("src.cli.setup_cli.scrape_website")
    @patch("src.cli.setup_cli.get_reference_document_by_source_url")
    @patch("src.config.get_settings")
    @patch("src.db.client.get_supabase_client")
    @patch("src.cli.setup_cli.questionary.select")
    @patch("src.cli.setup_cli.typer.confirm")
    @patch("src.cli.setup_cli.typer.prompt")
    @patch("src.cli.setup_cli.typer.echo")
    def test_setup_resume_when_ref_doc_exists(
        self,
        mock_echo,
        mock_prompt,
        mock_confirm,
        mock_questionary_select,
        mock_get_supabase,
        mock_get_settings,
        mock_get_ref_doc,
        mock_scrape,
        mock_build_ref,
        mock_create_ref_doc,
        mock_create_bot,
        mock_get_scraped_pages,
    ):
        """When a reference doc already exists for the URL, skip scrape/build/store and resume at action menu then tone + Facebook."""
        mock_get_scraped_pages.return_value = [{"id": "page1"}]  # already indexed
        mock_get_ref_doc.return_value = {
            "id": "existing-doc-456",
            "source_url": "https://example.com",
            "content": "# Existing doc content",
        }
        mock_confirm.return_value = True
        mock_create_bot.return_value = MagicMock()
        mock_questionary_select.return_value.ask.side_effect = [
            ACTION_CONTINUE,
            "Friendly",
        ]
        mock_prompt.side_effect = [
            "https://example.com",
            "789012345678901",  # valid 15-digit page ID
            VALID_PAGE_ACCESS_TOKEN,
            VALID_VERIFY_TOKEN,
        ]
        setup()
        # Lookup was called with normalized URL
        mock_get_ref_doc.assert_called_once_with("https://example.com")
        # Scrape and build were skipped (ref doc and page index both exist)
        mock_scrape.assert_not_called()
        mock_build_ref.assert_not_called()
        mock_create_ref_doc.assert_not_called()
        # Bot was created with existing reference doc id
        mock_create_bot.assert_called_once()
        assert mock_create_bot.call_args[1]["reference_doc_id"] == "existing-doc-456"
        assert mock_create_bot.call_args[1]["tone"] == "Friendly"
        assert mock_create_bot.call_args[1]["page_id"] == "789012345678901"

    @patch("src.cli.setup_cli.create_page_chunks")
    @patch("src.cli.setup_cli.create_scraped_page")
    @patch("src.cli.setup_cli.generate_embeddings", new_callable=AsyncMock)
    @patch("src.cli.setup_cli.get_scraped_pages_by_reference_doc")
    @patch("src.cli.setup_cli.create_bot_configuration")
    @patch("src.cli.setup_cli.build_reference_document")
    @patch("src.cli.setup_cli.scrape_website")
    @patch("src.cli.setup_cli.get_reference_document_by_source_url")
    @patch("src.config.get_settings")
    @patch("src.db.client.get_supabase_client")
    @patch("src.cli.setup_cli.questionary.select")
    @patch("src.cli.setup_cli.typer.prompt")
    @patch("src.cli.setup_cli.typer.echo")
    def test_setup_existing_doc_no_pages_indexed_scrapes_and_indexes_only(
        self,
        mock_echo,
        mock_prompt,
        mock_questionary_select,
        mock_get_supabase,
        mock_get_settings,
        mock_get_ref_doc,
        mock_scrape,
        mock_build_ref,
        mock_create_bot,
        mock_get_scraped_pages,
        mock_generate_embeddings,
        mock_create_scraped_page,
        mock_create_page_chunks,
    ):
        """When ref doc exists but no pages indexed, scrape and index pages without modifying reference doc."""
        mock_get_ref_doc.return_value = {
            "id": "existing-doc-456",
            "source_url": "https://example.com",
            "content": "# Existing doc content",
        }
        mock_get_scraped_pages.return_value = []  # no pages indexed yet
        mock_scrape.return_value = ScrapeResult(
            pages=[
                MagicMock(
                    url="https://example.com",
                    normalized_url="https://example.com",
                    title="Page",
                    content="Some content " * 100,
                    word_count=100,
                    scraped_at=MagicMock(),
                )
            ],
            chunks=["chunk1"],
            content_hash="h",
        )
        mock_create_scraped_page.return_value = "scraped-page-1"
        mock_generate_embeddings.return_value = [[0.1] * 1536]  # one embedding per chunk
        mock_questionary_select.return_value.ask.side_effect = [ACTION_EXIT]
        mock_prompt.side_effect = ["https://example.com"]
        setup()
        mock_get_ref_doc.assert_called_once_with("https://example.com")
        mock_get_scraped_pages.assert_called_once_with("existing-doc-456")
        mock_scrape.assert_called_once_with("https://example.com")
        mock_build_ref.assert_not_called()
        mock_create_scraped_page.assert_called()
        mock_create_bot.assert_not_called()

    @patch("src.cli.setup_cli.get_scraped_pages_by_reference_doc")
    @patch("src.cli.setup_cli.create_bot_configuration")
    @patch("src.cli.setup_cli.get_reference_document_by_source_url")
    @patch("src.config.get_settings")
    @patch("src.db.client.get_supabase_client")
    @patch("src.cli.setup_cli.questionary.select")
    @patch("src.cli.setup_cli.typer.prompt")
    @patch("src.cli.setup_cli.typer.echo")
    def test_setup_exit_from_menu(
        self,
        mock_echo,
        mock_prompt,
        mock_questionary_select,
        mock_get_supabase,
        mock_get_settings,
        mock_get_ref_doc,
        mock_create_bot,
        mock_get_scraped_pages,
    ):
        """When user selects Exit from action menu, setup exits without creating bot."""
        mock_get_scraped_pages.return_value = [{"id": "page1"}]  # already indexed
        mock_get_ref_doc.return_value = {
            "id": "existing-doc-456",
            "source_url": "https://example.com",
            "content": "# Existing doc content",
        }
        mock_questionary_select.return_value.ask.side_effect = [ACTION_EXIT]
        mock_prompt.side_effect = ["https://example.com"]
        setup()
        mock_create_bot.assert_not_called()

    @patch("src.cli.setup_cli.create_bot_configuration")
    @patch("src.cli.setup_cli.create_reference_document")
    @patch("src.cli.setup_cli.build_reference_document")
    @patch("src.cli.setup_cli.scrape_website")
    @patch("src.cli.setup_cli.get_reference_document_by_source_url")
    @patch("src.config.get_settings")
    @patch("src.db.client.get_supabase_client")
    @patch("src.cli.setup_cli.questionary.select")
    @patch("src.cli.setup_cli.typer.confirm")
    @patch("src.cli.setup_cli.typer.prompt")
    @patch("src.cli.setup_cli.typer.echo")
    def test_setup_aborts_when_confirmation_no(
        self,
        mock_echo,
        mock_prompt,
        mock_confirm,
        mock_questionary_select,
        mock_get_supabase,
        mock_get_settings,
        mock_get_ref_doc,
        mock_scrape,
        mock_build_ref,
        mock_create_ref_doc,
        mock_create_bot,
    ):
        """When user answers no to 'Do these look correct?', setup aborts and does not create bot."""
        mock_get_ref_doc.return_value = None
        mock_confirm.return_value = False  # user says no
        mock_settings = MagicMock()
        mock_settings.copilot_cli_host = "http://localhost:5909"
        mock_settings.copilot_enabled = True
        mock_get_settings.return_value = mock_settings
        mock_scrape.return_value = ScrapeResult(pages=[], chunks=["chunk1"], content_hash="h")
        mock_build_ref.return_value = "# Doc"
        mock_create_ref_doc.return_value = "doc-123"
        mock_questionary_select.return_value.ask.side_effect = [
            ACTION_CONTINUE,
            "Professional",
        ]
        mock_prompt.side_effect = [
            "https://example.com",
            VALID_PAGE_ID,
            VALID_PAGE_ACCESS_TOKEN,
            VALID_VERIFY_TOKEN,
        ]
        with pytest.raises(typer.Exit):
            setup()
        mock_create_bot.assert_not_called()
        # Should have echoed aborted message
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("Aborted" in call for call in echo_calls)

    @patch("src.cli.setup_cli.create_bot_configuration")
    @patch("src.cli.setup_cli.create_reference_document")
    @patch("src.cli.setup_cli.build_reference_document")
    @patch("src.cli.setup_cli.scrape_website")
    @patch("src.cli.setup_cli.get_reference_document_by_source_url")
    @patch("src.config.get_settings")
    @patch("src.db.client.get_supabase_client")
    @patch("src.cli.setup_cli.questionary.select")
    @patch("src.cli.setup_cli.typer.confirm")
    @patch("src.cli.setup_cli.typer.prompt")
    @patch("src.cli.setup_cli.typer.echo")
    def test_setup_writes_webhook_info_file(
        self,
        mock_echo,
        mock_prompt,
        mock_confirm,
        mock_questionary_select,
        mock_get_supabase,
        mock_get_settings,
        mock_get_ref_doc,
        mock_scrape,
        mock_build_ref,
        mock_create_ref_doc,
        mock_create_bot,
        tmp_path,
    ):
        """After successful setup, WEBHOOK_INFO.txt is written with callback URL, verify token, page ID."""
        # Patch _project_root to tmp_path so we can read the written file
        with patch("src.cli.setup_cli._project_root", tmp_path):
            mock_get_ref_doc.return_value = None
            mock_confirm.return_value = True
            mock_settings = MagicMock()
            mock_settings.copilot_cli_host = "http://localhost:5909"
            mock_settings.copilot_enabled = True
            mock_get_settings.return_value = mock_settings
            mock_scrape.return_value = ScrapeResult(pages=[], chunks=["chunk1"], content_hash="h")
            mock_build_ref.return_value = "# Doc"
            mock_create_ref_doc.return_value = "doc-123"
            mock_create_bot.return_value = MagicMock()
            mock_questionary_select.return_value.ask.side_effect = [
                ACTION_CONTINUE,
                "Professional",
            ]
            mock_prompt.side_effect = [
                "https://example.com",
                VALID_PAGE_ID,
                VALID_PAGE_ACCESS_TOKEN,
                VALID_VERIFY_TOKEN,
            ]
            setup()

        webhook_file = tmp_path / "WEBHOOK_INFO.txt"
        assert webhook_file.exists()
        content = webhook_file.read_text(encoding="utf-8")
        assert "FACEBOOK WEBHOOK CONFIGURATION" in content
        assert "Callback URL: https://YOUR-APP-NAME.railway.app/webhook" in content
        assert f"Verify Token: {VALID_VERIFY_TOKEN}" in content
        assert f"Page ID: {VALID_PAGE_ID}" in content
        assert "Generated:" in content
        assert "messages (required)" in content

    @patch("src.cli.setup_cli.create_bot_configuration")
    @patch("src.cli.setup_cli.create_reference_document")
    @patch("src.cli.setup_cli.build_reference_document")
    @patch("src.cli.setup_cli.scrape_website")
    @patch("src.cli.setup_cli.get_reference_document_by_source_url")
    @patch("src.config.get_settings")
    @patch("src.db.client.get_supabase_client")
    @patch("src.cli.setup_cli._run_test_repl")
    @patch("src.cli.setup_cli.questionary.select")
    @patch("src.cli.setup_cli.typer.confirm")
    @patch("src.cli.setup_cli.typer.prompt")
    @patch("src.cli.setup_cli.typer.echo")
    def test_setup_test_bot_then_continue(
        self,
        mock_echo,
        mock_prompt,
        mock_confirm,
        mock_questionary_select,
        mock_run_test_repl,
        mock_get_supabase,
        mock_get_settings,
        mock_get_ref_doc,
        mock_scrape,
        mock_build_ref,
        mock_create_ref_doc,
        mock_create_bot,
    ):
        """User can select Test the bot, then Continue; bot is created after."""
        mock_get_ref_doc.return_value = None
        mock_confirm.return_value = True
        mock_settings = MagicMock()
        mock_settings.copilot_cli_host = "http://localhost:5909"
        mock_settings.copilot_enabled = True
        mock_get_settings.return_value = mock_settings
        mock_scrape.return_value = ScrapeResult(pages=[], chunks=["chunk1"], content_hash="h")
        mock_build_ref.return_value = "# Doc"
        mock_create_ref_doc.return_value = "doc-123"
        mock_create_bot.return_value = MagicMock()
        # First: Test the bot; second: Continue. Then tone for bot, then Facebook prompts.
        mock_questionary_select.return_value.ask.side_effect = [
            ACTION_TEST_BOT,
            "Professional",  # tone for testing
            ACTION_CONTINUE,
            "Friendly",  # tone for bot
        ]
        mock_prompt.side_effect = [
            "https://example.com",
            VALID_PAGE_ID,
            VALID_PAGE_ACCESS_TOKEN,
            VALID_VERIFY_TOKEN,
        ]
        setup()
        mock_run_test_repl.assert_called_once_with(
            "# Doc", "Professional", "doc-123", "https://example.com"
        )
        mock_create_bot.assert_called_once()
        assert mock_create_bot.call_args[1]["tone"] == "Friendly"

    @patch("src.cli.setup_cli.get_reference_document_by_source_url")
    @patch("src.cli.setup_cli.typer.prompt")
    @patch("src.cli.setup_cli.typer.echo")
    def test_test_cmd_no_ref_doc(self, mock_echo, mock_prompt, mock_get_ref_doc):
        """Standalone test command exits with message when no reference doc for URL."""
        mock_get_ref_doc.return_value = None
        mock_prompt.return_value = "https://example.com"
        with pytest.raises(typer.Exit):
            cli_test_command()
        # Should have echoed "No reference document found..."
        assert any(
            "No reference document" in str(call) for call in mock_echo.call_args_list
        )

    @patch("src.cli.setup_cli._run_test_repl")
    @patch("src.cli.setup_cli.get_reference_document_by_source_url")
    @patch("src.cli.setup_cli.questionary.select")
    @patch("src.cli.setup_cli.typer.prompt")
    @patch("src.cli.setup_cli.typer.echo")
    def test_test_cmd_with_ref_doc_runs_repl(
        self,
        mock_echo,
        mock_prompt,
        mock_questionary_select,
        mock_get_ref_doc,
        mock_run_test_repl,
    ):
        """Standalone test command runs REPL when reference doc exists."""
        mock_get_ref_doc.return_value = {
            "id": "doc-1",
            "source_url": "https://example.com",
            "content": "# Doc content",
        }
        mock_prompt.return_value = "https://example.com"
        mock_questionary_select.return_value.ask.return_value = "Professional"
        cli_test_command()
        mock_run_test_repl.assert_called_once_with(
            "# Doc content", "Professional", "doc-1", "https://example.com"
        )


class TestPromptWithValidation:
    """Test _prompt_with_validation retry loop and exit behavior."""

    @patch("src.cli.setup_cli.typer.echo")
    @patch("src.cli.setup_cli.typer.prompt")
    def test_returns_value_when_valid_on_first_try(self, mock_prompt, mock_echo):
        """Valid input on first try returns immediately."""
        mock_prompt.return_value = "123456789012345"
        result = _prompt_with_validation(
            "Page ID",
            _validate_page_id,
            "Invalid",
        )
        assert result == "123456789012345"
        mock_prompt.assert_called_once()

    @patch("src.cli.setup_cli.typer.echo")
    @patch("src.cli.setup_cli.typer.prompt")
    def test_retries_on_invalid_then_accepts_valid(self, mock_prompt, mock_echo):
        """Invalid then valid input returns after retry."""
        mock_prompt.side_effect = ["bad", "123456789012345"]
        result = _prompt_with_validation(
            "Page ID",
            _validate_page_id,
            "Invalid Page ID format.",
        )
        assert result == "123456789012345"
        assert mock_prompt.call_count == 2
        # Error message and attempts remaining should have been echoed
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("Invalid" in call for call in echo_calls)
        assert any("attempts remaining" in call for call in echo_calls)

    @patch("src.cli.setup_cli.typer.echo")
    @patch("src.cli.setup_cli.typer.prompt")
    def test_exits_after_max_attempts(self, mock_prompt, mock_echo):
        """After max_attempts invalid inputs, raises typer.Exit(1)."""
        mock_prompt.return_value = "invalid"
        with pytest.raises(typer.Exit) as exc_info:
            _prompt_with_validation(
                "Page ID",
                _validate_page_id,
                "Invalid.",
                max_attempts=3,
            )
        assert exc_info.value.exit_code == 1
        assert mock_prompt.call_count == 3
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("Maximum attempts reached" in call for call in echo_calls)


class TestShowFacebookCredentialHelp:
    """Test _show_facebook_credential_help echoes expected content per type."""

    @patch("src.cli.setup_cli.typer.echo")
    def test_page_id_help_content(self, mock_echo):
        """page_id help includes Page ID instructions."""
        _show_facebook_credential_help("page_id")
        all_echoed = " ".join(
            str(c[0][0]) for c in mock_echo.call_args_list if c[0]
        )
        assert "How to Find Your Facebook Page ID" in all_echoed
        assert "developers.facebook.com" in all_echoed
        assert "Access Tokens" in all_echoed

    @patch("src.cli.setup_cli.typer.echo")
    def test_access_token_help_content(self, mock_echo):
        """access_token help includes token instructions."""
        _show_facebook_credential_help("access_token")
        all_echoed = " ".join(
            str(c[0][0]) for c in mock_echo.call_args_list if c[0]
        )
        assert "How to Get Page Access Token" in all_echoed
        assert "EAAA" in all_echoed
        assert "Generate Token" in all_echoed

    @patch("src.cli.setup_cli.typer.echo")
    def test_verify_token_help_content(self, mock_echo):
        """verify_token help includes verify token explanation."""
        _show_facebook_credential_help("verify_token")
        all_echoed = " ".join(
            str(c[0][0]) for c in mock_echo.call_args_list if c[0]
        )
        assert "About Verify Token" in all_echoed
        assert "openssl rand" in all_echoed
        assert "8-100 characters" in all_echoed


class TestPromptWithHelp:
    """Test _prompt_with_help: '?' triggers help and re-prompts; invalid re-prompts."""

    @patch("src.cli.setup_cli._show_facebook_credential_help")
    @patch("src.cli.setup_cli.typer.echo")
    @patch("src.cli.setup_cli.typer.prompt")
    def test_question_mark_shows_help_and_reprompts(self, mock_prompt, mock_echo, mock_help):
        """Typing '?' shows help then prompts again until valid."""
        mock_prompt.side_effect = ["?", "123456789012345"]
        result = _prompt_with_help(
            "Page ID",
            "page_id",
            validator=_validate_page_id,
        )
        assert result == "123456789012345"
        mock_help.assert_called_once_with("page_id")
        assert mock_prompt.call_count == 2

    @patch("src.cli.setup_cli.typer.echo")
    @patch("src.cli.setup_cli.typer.prompt")
    def test_invalid_input_shows_error_and_reprompts(self, mock_prompt, mock_echo):
        """Invalid input shows error message and prompts again."""
        mock_prompt.side_effect = ["short", "verify-token-12"]
        result = _prompt_with_help(
            "Verify Token",
            "verify_token",
            validator=_validate_verify_token,
        )
        assert result == "verify-token-12"
        assert mock_prompt.call_count == 2
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        assert any("Invalid format" in call for call in echo_calls)

    @patch("src.cli.setup_cli.typer.echo")
    @patch("src.cli.setup_cli.typer.prompt")
    def test_valid_input_returns_without_help(self, mock_prompt, mock_echo):
        """Valid input on first try returns without calling help."""
        mock_prompt.return_value = "123456789012345"
        result = _prompt_with_help(
            "Page ID",
            "page_id",
            validator=_validate_page_id,
        )
        assert result == "123456789012345"
        mock_prompt.assert_called_once()


class TestValidationFunctions:
    """Test Facebook credential validation helpers."""

    def test_validate_page_id_valid_15_digits(self):
        assert _validate_page_id("123456789012345") is True

    def test_validate_page_id_valid_17_digits(self):
        assert _validate_page_id("12345678901234567") is True

    def test_validate_page_id_invalid_short(self):
        assert _validate_page_id("12345678901234") is False

    def test_validate_page_id_invalid_non_digits(self):
        assert _validate_page_id("12345678901234a") is False
        assert _validate_page_id("page-123") is False

    def test_validate_page_id_strips_whitespace(self):
        assert _validate_page_id("  123456789012345  ") is True

    def test_validate_page_access_token_valid(self):
        assert _validate_page_access_token("EAAA" + "x" * 100) is True

    def test_validate_page_access_token_invalid_short(self):
        assert _validate_page_access_token("EAAAshort") is False

    def test_validate_page_access_token_invalid_prefix(self):
        assert _validate_page_access_token("EAAB" + "x" * 100) is False

    def test_validate_verify_token_valid(self):
        assert _validate_verify_token("verify-123") is True
        assert _validate_verify_token("my_bot_token_2024") is True
        assert _validate_verify_token("a" * 8) is True
        assert _validate_verify_token("a" * 100) is True

    def test_validate_verify_token_invalid_too_short(self):
        assert _validate_verify_token("short") is False

    def test_validate_verify_token_invalid_special_chars(self):
        assert _validate_verify_token("token@123") is False
        assert _validate_verify_token("token with space") is False


class TestRunTestReplPersistence:
    """Test that _run_test_repl creates test session and persists messages."""

    @patch("src.cli.setup_cli.typer.prompt")
    @patch("src.cli.setup_cli.typer.echo")
    @patch("src.cli.setup_cli.save_test_message")
    @patch("src.cli.setup_cli.create_test_session")
    @patch("src.cli.setup_cli.MessengerAgentService")
    def test_create_test_session_and_save_test_message_called(
        self,
        mock_agent_class,
        mock_create_session,
        mock_save_message,
        mock_echo,
        mock_prompt,
    ):
        """Test the bot path invokes create_test_session and save_test_message."""
        mock_create_session.return_value = "sess-1"
        mock_agent = MagicMock()

        async def fake_respond(_ctx, msg):
            return AgentResponse(
                message="Hey",
                confidence=0.9,
                requires_escalation=False,
                escalation_reason=None,
            )

        mock_agent.respond = fake_respond
        mock_agent_class.return_value = mock_agent
        mock_prompt.side_effect = ["Hi", "quit"]

        _run_test_repl(
            ref_doc_content="# Doc",
            tone="Professional",
            reference_doc_id="doc-123",
            source_url="https://example.com",
        )

        mock_create_session.assert_called_once_with(
            "doc-123", "https://example.com", "Professional"
        )
        mock_save_message.assert_called_once_with(
            test_session_id="sess-1",
            user_message="Hi",
            response_text="Hey",
            confidence=0.9,
            requires_escalation=False,
            escalation_reason=None,
        )

    @patch("src.cli.setup_cli.MessengerAgentService")
    @patch("src.cli.setup_cli.typer.prompt")
    @patch("src.cli.setup_cli.typer.echo")
    @patch("src.cli.setup_cli.save_test_message")
    @patch("src.cli.setup_cli.create_test_session")
    def test_when_create_test_session_fails_no_save_test_message(
        self, mock_create_session, mock_save_message, mock_echo, mock_prompt, mock_agent_class
    ):
        """When create_test_session fails, REPL runs but save_test_message is never called."""
        mock_create_session.side_effect = Exception("Supabase unavailable")
        mock_prompt.return_value = "quit"
        mock_agent_class.return_value = MagicMock()

        _run_test_repl(
            ref_doc_content="# Doc",
            tone="Casual",
            reference_doc_id="doc-456",
            source_url="https://example.org",
        )

        mock_create_session.assert_called_once_with(
            "doc-456", "https://example.org", "Casual"
        )
        mock_save_message.assert_not_called()
