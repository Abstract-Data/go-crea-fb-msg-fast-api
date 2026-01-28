"""Tests for setup CLI."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import typer

from src.cli.setup_cli import setup


class TestSetupCLI:
    """Test setup CLI command."""
    
    @patch('src.cli.setup_cli.create_bot_configuration')
    @patch('src.cli.setup_cli.create_reference_document')
    @patch('src.cli.setup_cli.build_reference_doc')
    @patch('src.cli.setup_cli.scrape_website')
    @patch('src.cli.setup_cli.get_settings')
    @patch('src.cli.setup_cli.get_supabase_client')
    @patch('src.cli.setup_cli.CopilotService')
    @patch('src.cli.setup_cli.typer.prompt')
    @patch('src.cli.setup_cli.typer.echo')
    def test_setup_complete_flow(
        self,
        mock_echo,
        mock_prompt,
        mock_copilot_service,
        mock_get_supabase,
        mock_get_settings,
        mock_scrape,
        mock_build_ref,
        mock_create_ref_doc,
        mock_create_bot
    ):
        """Test complete setup flow."""
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.copilot_cli_host = "http://localhost:5909"
        mock_settings.copilot_enabled = True
        mock_get_settings.return_value = mock_settings
        
        # Mock Supabase
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase
        
        # Mock Copilot service
        mock_copilot = MagicMock()
        mock_copilot_service.return_value = mock_copilot
        
        # Mock scraping
        mock_scrape.return_value = ["chunk1", "chunk2", "chunk3"]
        
        # Mock reference doc building
        mock_build_ref.return_value = ("# Reference Document", "hash123")
        
        # Mock database operations
        mock_create_ref_doc.return_value = "doc-123"
        mock_create_bot.return_value = MagicMock()
        
        # Mock typer prompts - provide enough values for all prompts
        mock_prompt.side_effect = [
            "https://example.com",  # website_url
            "Professional",  # tone (has default)
            "page-123",  # page_id
            "token-123",  # page_access_token
            "verify-123"  # verify_token (has default)
        ]
        
        # Run setup
        setup()
        
        # Verify scraping was called
        mock_scrape.assert_called_once_with("https://example.com")
        
        # Verify reference doc was built
        mock_build_ref.assert_called_once()
        
        # Verify database operations
        mock_create_ref_doc.assert_called_once()
        mock_create_bot.assert_called_once()
    
    @patch('src.cli.setup_cli.get_settings')
    @patch('src.cli.setup_cli.get_supabase_client')
    @patch('src.cli.setup_cli.CopilotService')
    @patch('src.cli.setup_cli.typer.prompt')
    @patch('src.cli.setup_cli.typer.echo')
    @patch('src.cli.setup_cli.scrape_website')
    def test_setup_scraping_error(
        self,
        mock_scrape,
        mock_echo,
        mock_prompt,
        mock_copilot_service,
        mock_get_supabase,
        mock_get_settings
    ):
        """Test error handling when scraping fails."""
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
        error_calls = [call for call in mock_echo.call_args_list if "Error" in str(call)]
        assert len(error_calls) > 0
    
    @patch('src.cli.setup_cli.get_settings')
    @patch('src.cli.setup_cli.get_supabase_client')
    @patch('src.cli.setup_cli.CopilotService')
    @patch('src.cli.setup_cli.typer.prompt')
    @patch('src.cli.setup_cli.typer.echo')
    @patch('src.cli.setup_cli.scrape_website')
    @patch('src.cli.setup_cli.build_reference_doc')
    def test_setup_reference_doc_error(
        self,
        mock_build_ref,
        mock_scrape,
        mock_echo,
        mock_prompt,
        mock_copilot_service,
        mock_get_supabase,
        mock_get_settings
    ):
        """Test error handling when reference doc generation fails."""
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
        error_calls = [call for call in mock_echo.call_args_list if "Error" in str(call)]
        assert len(error_calls) > 0
    
    @patch('src.cli.setup_cli.get_settings')
    @patch('src.cli.setup_cli.get_supabase_client')
    @patch('src.cli.setup_cli.CopilotService')
    @patch('src.cli.setup_cli.typer.prompt')
    @patch('src.cli.setup_cli.typer.echo')
    @patch('src.cli.setup_cli.scrape_website')
    @patch('src.cli.setup_cli.build_reference_doc')
    @patch('src.cli.setup_cli.create_reference_document')
    def test_setup_database_error(
        self,
        mock_create_ref_doc,
        mock_build_ref,
        mock_scrape,
        mock_echo,
        mock_prompt,
        mock_copilot_service,
        mock_get_supabase,
        mock_get_settings
    ):
        """Test error handling when database operations fail."""
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
            "verify-123"
        ]
        mock_scrape.return_value = ["chunk1"]
        mock_build_ref.return_value = ("# Doc", "hash")
        mock_create_ref_doc.side_effect = Exception("Database error")
        
        with pytest.raises(typer.Exit):
            setup()
        
        # Verify error was echoed
        error_calls = [call for call in mock_echo.call_args_list if "Error" in str(call)]
        assert len(error_calls) > 0
    
    @patch('src.cli.setup_cli.create_bot_configuration')
    @patch('src.cli.setup_cli.create_reference_document')
    @patch('src.cli.setup_cli.build_reference_doc')
    @patch('src.cli.setup_cli.scrape_website')
    @patch('src.cli.setup_cli.get_settings')
    @patch('src.cli.setup_cli.get_supabase_client')
    @patch('src.cli.setup_cli.CopilotService')
    @patch('src.cli.setup_cli.typer.prompt')
    @patch('src.cli.setup_cli.typer.echo')
    def test_setup_tone_selection(
        self,
        mock_echo,
        mock_prompt,
        mock_copilot_service,
        mock_get_supabase,
        mock_get_settings,
        mock_scrape,
        mock_build_ref,
        mock_create_ref_doc,
        mock_create_bot
    ):
        """Test tone selection step."""
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.copilot_cli_host = "http://localhost:5909"
        mock_settings.copilot_enabled = True
        mock_get_settings.return_value = mock_settings
        
        mock_prompt.side_effect = [
            "https://example.com",
            "Professional",  # tone
            "page-123",
            "token-123",
            "verify-123"
        ]
        mock_scrape.return_value = ["chunk1"]
        mock_build_ref.return_value = ("# Doc", "hash")
        mock_create_ref_doc.return_value = "doc-123"
        mock_create_bot.return_value = MagicMock()
        
        setup()
        
        # Verify tone was used in bot configuration
        bot_call = mock_create_bot.call_args
        assert bot_call[1]["tone"] == "Professional"
    
    @patch('src.cli.setup_cli.create_bot_configuration')
    @patch('src.cli.setup_cli.create_reference_document')
    @patch('src.cli.setup_cli.build_reference_doc')
    @patch('src.cli.setup_cli.scrape_website')
    @patch('src.cli.setup_cli.get_settings')
    @patch('src.cli.setup_cli.get_supabase_client')
    @patch('src.cli.setup_cli.CopilotService')
    @patch('src.cli.setup_cli.typer.prompt')
    @patch('src.cli.setup_cli.typer.echo')
    def test_setup_prints_webhook_url(
        self,
        mock_echo,
        mock_prompt,
        mock_copilot_service,
        mock_get_supabase,
        mock_get_settings,
        mock_scrape,
        mock_build_ref,
        mock_create_ref_doc,
        mock_create_bot
    ):
        """Test that setup prints webhook URL and next steps."""
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.copilot_cli_host = "http://localhost:5909"
        mock_settings.copilot_enabled = True
        mock_get_settings.return_value = mock_settings
        
        mock_prompt.side_effect = [
            "https://example.com",
            "Professional",
            "page-123",
            "token-123",
            "verify-123"
        ]
        mock_scrape.return_value = ["chunk1"]
        mock_build_ref.return_value = ("# Doc", "hash")
        mock_create_ref_doc.return_value = "doc-123"
        mock_create_bot.return_value = MagicMock()
        
        setup()
        
        # Verify webhook URL and next steps were printed
        echo_calls = [str(call) for call in mock_echo.call_args_list]
        webhook_mentions = [call for call in echo_calls if "webhook" in call.lower()]
        assert len(webhook_mentions) > 0
