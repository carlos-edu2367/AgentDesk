# AgentDesk User Guide

## Start the App

In development, start the backend and frontend separately, then launch Electron. In packaged mode, Electron starts the backend automatically and the Startup screen waits for `/api/health`.

## Configure Providers

Use Providers to add Ollama or OpenRouter. Ollama can be unavailable; the app should show a friendly error. OpenRouter requires an API key, and the key should only appear masked after saving.

## Create an Agent

Open Agents, create an agent, choose provider/model, write a system prompt, and select capabilities. Critical capabilities such as terminal and filesystem write still require manual approval unless the execution uses auto approval.

## Run an Agent

Open Executions, choose Run Agent, select an agent, enter a message, choose approval mode, and start. Execution detail shows timeline, approvals, audit data, and export actions.

## Workspaces and Tools

Workspaces define allowed filesystem paths. Tools should only operate inside authorized workspaces and should generate audit logs.

## Memory, Skills, Plugins, MCP, Teams

Memory stores reusable context. Skills add prompt behavior. Plugins add local tools and skills from trusted folders. MCP stdio connects local MCP servers. Teams run the initial `leader_managed` multiagent strategy.
