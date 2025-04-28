# bot.py - Graphite Quest Discord Bot for creating quests
# This script sets up a Discord bot with a /quest create command and stores quest data in Supabase.

# Import required libraries
import discord
from discord import app_commands
from supabase import create_client, Client
import os
from dotenv import load_dotenv  # Added to load environment variables from a .env file

# Load environment variables from .env file
load_dotenv()

# Initialize Discord bot with required intents for slash commands
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Initialize Supabase client using environment variables
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),  # Supabase project URL
    os.getenv("SUPABASE_KEY")    # Supabase anon API key
)

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
    # Defer the response to avoid timeout while interacting with Supabase
    await interaction.response.defer()

    try:
        # Validate points input (must be between 1 and 1000)
        if points < 1 or points > 1000:
            await interaction.followup.send("Woof! Points must be between 1 and 1000. Try again!")
            return

        # Prepare quest data to insert into Supabase
        quest_data = {
            "title": title,
            "description": description,
            "creator_id": str(interaction.user.id),  # Store the Discord user ID as a string
            "points": points
        }

        # Insert the quest into the Supabase 'quests' table
        response = supabase.table("quests").insert(quest_data).execute()

        # Check if the insertion was successful
        if response.data:
            await interaction.followup.send(
                f"Woof! Quest created by {interaction.user.mention}, powered by Graphite!\n"
                f"**{title}**\n{description}\nReward: {points} points"
            )
        else:
            await interaction.followup.send("Woof! Something went wrong while creating the quest. Try again!")

    except Exception as e:
        # Handle any errors (e.g., database connection issues)
        await interaction.followup.send(f"Woof! An error occurred: {str(e)}")
        print(f"Error in quest_create: {e}")

# Run the bot using the Discord bot token from environment variables
client.run(os.getenv("DISCORD_TOKEN"))