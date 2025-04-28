# bot.py - Graphite Quest Discord Bot for creating quests
# This script sets up a Discord bot with a /quest create command and stores quest data in Neon (PostgreSQL).

# Import required libraries
import discord
from discord import app_commands
import os
from dotenv import load_dotenv  # Load environment variables from .env file
import psycopg2  # PostgreSQL driver for Neon
from psycopg2 import sql

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
        # Sync slash commands with Discord
        synced = await tree.sync()
        print(f"Synced {len(synced)} command(s)")
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
        """)
        cursor.execute(query, (title, description, str(interaction.user.id), points))
        conn.commit()

        # Send success message
        await interaction.followup.send(
            f"Woof! Quest created by {interaction.user.mention}, powered by Graphite!\n"
            f"**{title}**\n{description}\nReward: {points} points"
        )

    except Exception as e:
        # Handle any errors (e.g., database connection issues)
        await interaction.followup.send(f"Woof! An error occurred: {str(e)}")
        print(f"Error in quest_create: {e}")
        conn.rollback()

# Slash Command: /quest list
# Displays a list of all quests in the server
@tree.command(name="quest_list", description="View all quests with Graphite!")
async def quest_list(interaction: discord.Interaction):
    # Defer the response to avoid timeout while querying the database
    await interaction.response.defer()
    try:
        # Query all quests from the Neon 'quests' table, ordered by creation date
        query = sql.SQL("SELECT title, description, creator_id, points, created_at FROM quests ORDER BY created_at DESC")
        cursor.execute(query)
        quests = cursor.fetchall()

        # Check if there are any quests
        if not quests:
            await interaction.followup.send("Woof! No quests found. Create one with /quest create!")
            return

        # Format the list of quests
        quest_list = "Woof! Here are the quests I found:\n\n"
        for index, quest in enumerate(quests, 1):
            title, description, creator_id, points, created_at = quest
            # Try to fetch the creator's username; if not found, use the ID
            try:
                creator = await client.fetch_user(int(creator_id))
                creator_name = creator.display_name
            except discord.NotFound:
                creator_name = f"User ID: {creator_id} (not found)"
                qeury_list += (
                    f"**Quest {index}: {title}**\n"
                    f"Description: {description}\n"
                    f"Created by: {creator_name}\n"
                    f"Reward: {points} points\n"
                    f"Posted on: {created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                )

            # Send the formatted list
            await interaction.followup.send(quest_list)

    except Exception as e:
        # Handle any errors (e.g., database connection issues)
        await interaction.followup.send(f"Woof! An error occurred: {str(e)}")
        print(f"Error in quest_list: {e}")


# Run the bot using the Discord bot token from environment variables
client.run(os.getenv("DISCORD_TOKEN"))