"""Typer-based interactive setup CLI."""

import asyncio
import typer
from typing_extensions import Annotated

from src.services.scraper import scrape_website
from src.services.reference_doc import build_reference_doc
from src.services.copilot_service import CopilotService
from src.db.repository import create_bot_configuration, create_reference_document
from src.db.client import get_supabase_client
from src.config import get_settings

app = typer.Typer()


@app.command()
def setup():
    """
    Interactive setup:
    1) Ask for website
    2) Scrape + build reference doc via Copilot
    3) Ask for tone (with recommendations)
    4) Ask for Facebook Page config
    5) Persist bot config in Supabase
    """
    settings = get_settings()
    supabase = get_supabase_client()
    copilot = CopilotService(
        base_url=settings.copilot_cli_host,
        enabled=settings.copilot_enabled
    )
    
    # Step 1: Website URL
    website_url = typer.prompt("What website should the bot be based on?")
    
    typer.echo(f"Scraping {website_url}...")
    try:
        text_chunks = asyncio.run(scrape_website(website_url))
        typer.echo(f"✓ Scraped {len(text_chunks)} text chunks")
    except Exception as e:
        typer.echo(f"✗ Error scraping website: {e}", err=True)
        raise typer.Exit(1)
    
    # Step 2: Build reference doc
    typer.echo("Generating reference document via Copilot...")
    try:
        markdown_content, content_hash = asyncio.run(build_reference_doc(
            copilot, website_url, text_chunks
        ))
        typer.echo("✓ Reference document generated")
    except Exception as e:
        typer.echo(f"✗ Error generating reference doc: {e}", err=True)
        raise typer.Exit(1)
    
    # Step 3: Tone selection
    # TODO: Use Copilot to suggest tones from content
    recommended_tones = ["Professional", "Friendly", "Casual"]
    typer.echo(f"\nRecommended tones: {', '.join(recommended_tones)}")
    tone = typer.prompt("Select a tone", default="Professional")
    
    # Step 4: Facebook configuration
    page_id = typer.prompt("Facebook Page ID")
    page_access_token = typer.prompt("Facebook Page Access Token")
    verify_token = typer.prompt("Verify Token (for webhook)", default=typer.style("random-token-123", fg=typer.colors.YELLOW))
    
    # Step 5: Store reference document
    typer.echo("\nStoring reference document...")
    try:
        reference_doc_id = create_reference_document(
            content=markdown_content,
            source_url=website_url,
            content_hash=content_hash
        )
        typer.echo("✓ Reference document stored")
    except Exception as e:
        typer.echo(f"✗ Error storing reference document: {e}", err=True)
        raise typer.Exit(1)
    
    # Step 6: Create bot configuration
    typer.echo("\nCreating bot configuration...")
    try:
        bot_config = create_bot_configuration(
            page_id=page_id,
            website_url=website_url,
            reference_doc_id=reference_doc_id,
            tone=tone,
            facebook_page_access_token=page_access_token,
            facebook_verify_token=verify_token
        )
        typer.echo("✓ Bot configuration created")
    except Exception as e:
        typer.echo(f"✗ Error creating bot configuration: {e}", err=True)
        raise typer.Exit(1)
    
    # Step 7: Print webhook URL
    typer.echo("\n" + "="*60)
    typer.echo("✓ Setup complete!")
    typer.echo("\nNext steps:")
    typer.echo(f"1. Configure webhook URL in Facebook App settings:")
    typer.echo(f"   https://your-railway-url.railway.app/webhook")
    typer.echo(f"2. Set verify token: {verify_token}")
    typer.echo(f"3. Subscribe to 'messages' events")
    typer.echo("="*60)


if __name__ == "__main__":
    app()
