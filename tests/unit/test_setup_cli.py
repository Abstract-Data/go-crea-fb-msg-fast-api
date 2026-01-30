"""Tests for setup CLI."""

import pytest
import asyncio
import gc
import time
from unittest.mock import patch, MagicMock
import typer

from src.cli.setup_cli import (
    setup,
    test as cli_test_command,
    ACTION_CONTINUE,
    ACTION_EXIT,
    ACTION_TEST_BOT,
)


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
    @patch("src.cli.setup_cli.typer.prompt")
    @patch("src.cli.setup_cli.typer.echo")
    def test_setup_complete_flow(
        self,
        mock_echo,
        mock_prompt,
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
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.copilot_cli_host = "http://localhost:5909"
        mock_settings.copilot_enabled = True
        mock_get_settings.return_value = mock_settings

        # Mock Supabase
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        # Mock scraping
        mock_scrape.return_value = ["chunk1", "chunk2", "chunk3"]

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

        # Mock typer prompts: website (copy/paste), then Facebook fields only
        mock_prompt.side_effect = [
            "https://example.com",  # website_url
            "page-123",  # page_id
            "token-123",  # page_access_token
            "verify-123",  # verify_token
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
        mock_scrape.return_value = ["chunk1"]
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
        mock_scrape.return_value = ["chunk1"]
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
    @patch("src.cli.setup_cli.typer.prompt")
    @patch("src.cli.setup_cli.typer.echo")
    def test_setup_tone_selection(
        self,
        mock_echo,
        mock_prompt,
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
            "page-123",
            "token-123",
            "verify-123",
        ]
        mock_scrape.return_value = ["chunk1"]
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
    @patch("src.cli.setup_cli.typer.prompt")
    @patch("src.cli.setup_cli.typer.echo")
    def test_setup_prints_webhook_url(
        self,
        mock_echo,
        mock_prompt,
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
            "page-123",
            "token-123",
            "verify-123",
        ]
        mock_scrape.return_value = ["chunk1"]
        mock_build_ref.return_value = "# Doc"
        mock_create_ref_doc.return_value = "doc-123"
        mock_create_bot.return_value = MagicMock()

        setup()

        # Verify webhook URL and next steps were printed
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        webhook_mentions = [call for call in echo_calls if "webhook" in call.lower()]
        assert len(webhook_mentions) > 0

    @patch("src.cli.setup_cli.create_bot_configuration")
    @patch("src.cli.setup_cli.create_reference_document")
    @patch("src.cli.setup_cli.build_reference_document")
    @patch("src.cli.setup_cli.scrape_website")
    @patch("src.cli.setup_cli.get_reference_document_by_source_url")
    @patch("src.config.get_settings")
    @patch("src.db.client.get_supabase_client")
    @patch("src.cli.setup_cli.questionary.select")
    @patch("src.cli.setup_cli.typer.prompt")
    @patch("src.cli.setup_cli.typer.echo")
    def test_setup_resume_when_ref_doc_exists(
        self,
        mock_echo,
        mock_prompt,
        mock_questionary_select,
        mock_get_supabase,
        mock_get_settings,
        mock_get_ref_doc,
        mock_scrape,
        mock_build_ref,
        mock_create_ref_doc,
        mock_create_bot,
    ):
        """When a reference doc already exists for the URL, skip scrape/build/store and resume at action menu then tone + Facebook."""
        mock_get_ref_doc.return_value = {
            "id": "existing-doc-456",
            "source_url": "https://example.com",
            "content": "# Existing doc content",
        }
        mock_create_bot.return_value = MagicMock()
        mock_questionary_select.return_value.ask.side_effect = [
            ACTION_CONTINUE,
            "Friendly",
        ]
        mock_prompt.side_effect = [
            "https://example.com",
            "page-789",
            "token-789",
            "verify-789",
        ]
        setup()
        # Lookup was called with normalized URL
        mock_get_ref_doc.assert_called_once_with("https://example.com")
        # Scrape and build were skipped
        mock_scrape.assert_not_called()
        mock_build_ref.assert_not_called()
        mock_create_ref_doc.assert_not_called()
        # Bot was created with existing reference doc id
        mock_create_bot.assert_called_once()
        assert mock_create_bot.call_args[1]["reference_doc_id"] == "existing-doc-456"
        assert mock_create_bot.call_args[1]["tone"] == "Friendly"
        assert mock_create_bot.call_args[1]["page_id"] == "page-789"

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
    ):
        """When user selects Exit from action menu, setup exits without creating bot."""
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
    @patch("src.cli.setup_cli._run_test_repl")
    @patch("src.cli.setup_cli.questionary.select")
    @patch("src.cli.setup_cli.typer.prompt")
    @patch("src.cli.setup_cli.typer.echo")
    def test_setup_test_bot_then_continue(
        self,
        mock_echo,
        mock_prompt,
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
        mock_settings = MagicMock()
        mock_settings.copilot_cli_host = "http://localhost:5909"
        mock_settings.copilot_enabled = True
        mock_get_settings.return_value = mock_settings
        mock_scrape.return_value = ["chunk1"]
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
            "page-123",
            "token-123",
            "verify-123",
        ]
        setup()
        mock_run_test_repl.assert_called_once()
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
        mock_run_test_repl.assert_called_once_with("# Doc content", "Professional")
