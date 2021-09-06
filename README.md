# discord-eve-authenticator
A discord authentication bot used to tie discord identities to identities from the video game EVE Online. During a sensitive in-game operation, we needed to be able to verify that all members of our discord server were also members of a whitelisted group in the game. This bot allowed players to authenticate themselves by talking to the game's extensive API. Upon successful authentication, it would grant the member access to the sensitive areas of the discord server.

## agentbot.py 
This is the code for the discord bot. It talks to users and processes certain commands, and it grants privileges where needed. 

## SSO_euthenticator_app.py 
This is a web service which talks to the EVE Online API and updates a shared SQL database, linking the user's discord identity with their in-game identity.
