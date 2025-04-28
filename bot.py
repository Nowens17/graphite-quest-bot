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

# Run the bot using the Discord bot token from environment variables
client.run(os.getenv("DISCORD_TOKEN"))