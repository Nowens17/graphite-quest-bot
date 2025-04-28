# bot.py - Graphite Quest Discord Bot for creating, listing, claiming, and suggesting quests
# This script sets up a Discord bot with /quest create, /quest list (with pagination), /quest claim, and /quest suggest commands, storing data in Neon (PostgreSQL).

# Import required libraries
import discord
from discord import app_commands
import os
from dotenv import load_dotenv  # Load environment variables from .env file
import psycopg2  # PostgreSQL driver for Neon
from psycopg2 import sql
import requests  # For making API calls to Hugging Face
import json

# Load environment variables from .env file
load_dotenv()

# Initialize Discord bot with required intents for slash commands
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Initialize PostgreSQL connection to Neon
# DATABASE_URL should be set in environment variables (e.g., postgresql://username:password@host:port/neondb)
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cursor = conn.cursor()

# Event: Bot is ready and synced with Discord
@client.event
async def on_ready():
    print(f"Woof! {client.user} (Graphite Quest) is online!")
    try:
        # Sync commands for a specific guild (faster and more reliable than global sync)
        guild_id = YOUR_SERVER_ID  # Replace with your Discord server ID (e.g., from https://discord.gg/37tQBt5v)
        guild = discord.Object(id=guild_id)
        # Sync commands for the specified guild
        tree.copy_global_to(guild=guild)
        synced = await tree.sync(guild=guild)
        # Print the synced commands for debugging
        print(f"Synced {len(synced)} command(s) for guild {guild_id}: {[cmd.name for cmd in synced]}")
    except Exception as e:
        print(f"Error syncing commands: {e}")

# Slash Command: /quest create
# Allows users to create a quest with a title, description, and points
@tree.command(name="quest", description="Create a new quest with Graphite!")
@app_commands.describe(
    title="The title of the quest",
    description="A description of the quest",
    points="Reward points for completing the quest (1-1000)"
)
async def quest_create(interaction: discord.Interaction, title: str, description: str, points: int):
    # Defer the response to avoid timeout while interacting with the database
    await interaction.response.defer()

    try:
        # Validate points input (must be between 1 and 1000)
        if points < 1 or points > 1000:
            await interaction.followup.send("Woof! Points must be between 1 and 1000. Try again!")
            return

        # Insert the quest into the Neon 'quests' table
        query = sql.SQL("""
            INSERT INTO quests (title, description, creator_id, points)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """)
        cursor.execute(query, (title, description, str(interaction.user.id), points))
        quest_id = cursor.fetchone()[0]
        conn.commit()

        # Send success message
        await interaction.followup.send(
            f"Woof! Quest created by {interaction.user.mention}, powered by Graphite!\n"
            f"**{title}** (ID: {quest_id})\n{description}\nReward: {points} points"
        )

    except Exception as e:
        # Handle any errors (e.g., database connection issues)
        await interaction.followup.send(f"Woof! An error occurred: {str(e)}")
        print(f"Error in quest_create: {e}")
        conn.rollback()

# Slash Command: /quest list
# Displays a paginated list of all quests in the server
@tree.command(name="quest_list", description="View all quests with Graphite!")
@app_commands.describe(
    page="The page number to view (default is 1)"
)
async def quest_list(interaction: discord.Interaction, page: int = 1):
    # Defer the response to avoid timeout while querying the database
    await interaction.response.defer()

    try:
        # Validate page number
        if page < 1:
            await interaction.followup.send("Woof! Page number must be 1 or higher. Try again!")
            return

        # Define pagination settings
        quests_per_page = 5
        offset = (page - 1) * quests_per_page

        # Query the total number of quests for pagination
        cursor.execute("SELECT COUNT(*) FROM quests")
        total_quests = cursor.fetchone()[0]
        total_pages = (total_quests + quests_per_page - 1) // quests_per_page

        # Check if the page is valid
        if page > total_pages and total_quests > 0:
            await interaction.followup.send(f"Woof! Page {page} doesn’t exist. There are only {total_pages} pages!")
            return

        # Query quests for the current page, ordered by creation date
        query = sql.SQL("""
            SELECT id, title, description, creator_id, points, created_at
            FROM quests
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """)
        cursor.execute(query, (quests_per_page, offset))
        quests = cursor.fetchall()

        # Check if there are any quests
        if not quests:
            await interaction.followup.send("Woof! No quests found. Create one with /quest create!")
            return

        # Format the list of quests for the current page
        quest_list = f"Woof! Here are the quests I found (Page {page}/{total_pages}):\n\n"
        for quest in quests:
            quest_id, title, description, creator_id, points, created_at = quest
            # Try to fetch the creator's username; if not found, use the ID
            try:
                creator = await client.fetch_user(int(creator_id))
                creator_name = creator.display_name
            except discord.NotFound:
                creator_name = f"User ID {creator_id} (not found)"
            # Add the quest details to the message
            quest_list += (
                f"**Quest ID: {quest_id} | {title}**\n"
                f"Description: {description}\n"
                f"Created by: {creator_name}\n"
                f"Reward: {points} points\n"
                f"Posted on: {created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )

        # Add pagination instructions if there are more pages
        if total_pages > 1:
            quest_list += f"To see more, use /quest_list page:<number> (e.g., /quest_list page:{page + 1 if page < total_pages else 1})"

        # Send the formatted list
        await interaction.followup.send(quest_list)

    except Exception as e:
        # Handle any errors (e.g., database query issues)
        await interaction.followup.send(f"Woof! An error occurred while fetching quests: {str(e)}")
        print(f"Error in quest_list: {e}")

# Slash Command: /quest claim
# Allows users to claim a quest by its ID
@tree.command(name="quest_claim", description="Claim a quest with Graphite!")
@app_commands.describe(
    quest_id="The ID of the quest to claim (see /quest_list for IDs)"
)
async def quest_claim(interaction: discord.Interaction, quest_id: str):
    # Defer the response to avoid timeout while interacting with the database
    await interaction.response.defer()

    try:
        # Validate the quest_id format (should be a UUID)
        query = sql.SQL("SELECT title, creator_id FROM quests WHERE id = %s")
        cursor.execute(query, (quest_id,))
        quest = cursor.fetchone()
        if not quest:
            await interaction.followup.send("Woof! Quest not found. Check the ID and try again!")
            return

        title, creator_id = quest

        # Check if the user created the quest
        if creator_id == str(interaction.user.id):
            await interaction.followup.send("Woof! You can’t claim your own quest, silly!")
            return

        # Check if the user has already claimed the quest
        query = sql.SQL("SELECT id FROM quest_claims WHERE quest_id = %s AND user_id = %s")
        cursor.execute(query, (quest_id, str(interaction.user.id)))
        if cursor.fetchone():
            await interaction.followup.send(f"Woof! You’ve already claimed **{title}**. Find another quest!")
            return

        # Record the claim in the quest_claims table
        query = sql.SQL("""
            INSERT INTO quest_claims (quest_id, user_id)
            VALUES (%s, %s)
        """)
        cursor.execute(query, (quest_id, str(interaction.user.id)))
        conn.commit()

        # Send success message
        await interaction.followup.send(
            f"Woof! You’ve claimed **{title}**, {interaction.user.mention}! Good luck on your quest!"
        )

    except Exception as e:
        # Handle any errors (e.g., database connection issues, unique constraint violation)
        await interaction.followup.send(f"Woof! An error occurred while claiming the quest: {str(e)}")
        print(f"Error in quest_claim: {e}")
        conn.rollback()

# Slash Command: /quest suggest
# Suggests a quest idea based on a theme using Hugging Face's text generation API
@tree.command(name="quest_suggest", description="Get a quest idea from Graphite!")
@app_commands.describe(
    theme="The theme for the quest (e.g., fantasy, sci-fi, adventure)"
)
async def quest_suggest(interaction: discord.Interaction, theme: str):
    # Defer the response to avoid timeout while making the API call
    await interaction.response.defer()

    try:
        # Get the Hugging Face API token from environment variables
        api_token = os.getenv("HUGGINGFACE_TOKEN")
        if not api_token:
            await interaction.followup.send("Woof! My AI brain isn’t set up properly. Missing Hugging Face API token!")
            return

        # Set up the Hugging Face API endpoint and headers
        api_url = "https://api-inference.huggingface.co/models/distilgpt2"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }

        # Create a prompt for the AI to generate a quest title and description
        prompt = f"A {theme} quest: In a world of {theme}, a hero must "
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_length": 100,
                "num_return_sequences": 1,
                "temperature": 0.9,
                "top_p": 0.95
            }
        }

        # Make the API call to Hugging Face
        response = requests.post(api_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()  # Raise an error for bad status codes
        generated_text = response.json()[0]["generated_text"]

        # Extract a title and description from the generated text
        # Split the text into sentences and use the first as the title, the rest as the description
        sentences = generated_text.replace(prompt, "").strip().split(". ")
        title = sentences[0] if sentences else "A Mysterious Quest"
        description = ". ".join(sentences[1:]) if len(sentences) > 1 else "Embark on a thrilling adventure!"

        # Clean up the title and description (remove incomplete sentences)
        if not description.endswith("."):
            description = description.rsplit(" ", 1)[0] + "."
        title = title[:50]  # Limit title length for readability
        description = description[:200]  # Limit description length

        # Send the suggestion
        await interaction.followup.send(
            f"Woof! I’ve sniffed out a quest idea for you, {interaction.user.mention}!\n"
            f"**{title}** (Theme: {theme})\n"
            f"Description: {description}\n"
            f"Use /quest create to add it with your own points!"
        )

    except Exception as e:
        # Handle any errors (e.g., API failure, network issues)
        await interaction.followup.send(f"Woof! My AI brain got confused: {str(e)}")
        print(f"Error in quest_suggest: {e}")

# Run the bot using the Discord bot token from environment variables
client.run(os.getenv("DISCORD_TOKEN"))