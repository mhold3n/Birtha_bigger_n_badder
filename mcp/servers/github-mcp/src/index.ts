import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { Octokit } from '@octokit/rest';
import dotenv from 'dotenv';

// Load environment variables
dotenv.config();

interface GitHubConfig {
  token: string;
  owner?: string;
  repo?: string;
}

class GitHubMCPServer {
  private server: Server;
  private octokit: Octokit;
  private config: GitHubConfig;

  constructor() {
    this.config = {
      token: process.env.GITHUB_TOKEN || '',
      owner: process.env.GITHUB_OWNER,
      repo: process.env.GITHUB_REPO,
    };

    if (!this.config.token) {
      throw new Error('GITHUB_TOKEN environment variable is required');
    }

    this.octokit = new Octokit({
      auth: this.config.token,
    });

    this.server = new Server(
      {
        name: 'github-mcp-server',
        version: '0.1.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.setupHandlers();
  }

  private setupHandlers(): void {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      return {
        tools: [
          {
            name: 'search_repositories',
            description: 'Search for repositories on GitHub',
            inputSchema: {
              type: 'object',
              properties: {
                query: {
                  type: 'string',
                  description: 'Search query',
                },
                sort: {
                  type: 'string',
                  enum: ['stars', 'forks', 'help-wanted-issues', 'updated'],
                  description: 'Sort order',
                },
                order: {
                  type: 'string',
                  enum: ['asc', 'desc'],
                  description: 'Sort direction',
                },
                per_page: {
                  type: 'number',
                  minimum: 1,
                  maximum: 100,
                  description: 'Number of results per page',
                },
              },
              required: ['query'],
            },
          },
          {
            name: 'get_repository',
            description: 'Get information about a specific repository',
            inputSchema: {
              type: 'object',
              properties: {
                owner: {
                  type: 'string',
                  description: 'Repository owner',
                },
                repo: {
                  type: 'string',
                  description: 'Repository name',
                },
              },
              required: ['owner', 'repo'],
            },
          },
          {
            name: 'list_issues',
            description: 'List issues for a repository',
            inputSchema: {
              type: 'object',
              properties: {
                owner: {
                  type: 'string',
                  description: 'Repository owner',
                },
                repo: {
                  type: 'string',
                  description: 'Repository name',
                },
                state: {
                  type: 'string',
                  enum: ['open', 'closed', 'all'],
                  description: 'Issue state',
                },
                labels: {
                  type: 'string',
                  description: 'Comma-separated list of labels',
                },
                per_page: {
                  type: 'number',
                  minimum: 1,
                  maximum: 100,
                  description: 'Number of results per page',
                },
              },
              required: ['owner', 'repo'],
            },
          },
          {
            name: 'create_issue',
            description: 'Create a new issue',
            inputSchema: {
              type: 'object',
              properties: {
                owner: {
                  type: 'string',
                  description: 'Repository owner',
                },
                repo: {
                  type: 'string',
                  description: 'Repository name',
                },
                title: {
                  type: 'string',
                  description: 'Issue title',
                },
                body: {
                  type: 'string',
                  description: 'Issue body',
                },
                labels: {
                  type: 'array',
                  items: { type: 'string' },
                  description: 'Issue labels',
                },
                assignees: {
                  type: 'array',
                  items: { type: 'string' },
                  description: 'Issue assignees',
                },
              },
              required: ['owner', 'repo', 'title'],
            },
          },
          {
            name: 'list_pull_requests',
            description: 'List pull requests for a repository',
            inputSchema: {
              type: 'object',
              properties: {
                owner: {
                  type: 'string',
                  description: 'Repository owner',
                },
                repo: {
                  type: 'string',
                  description: 'Repository name',
                },
                state: {
                  type: 'string',
                  enum: ['open', 'closed', 'all'],
                  description: 'Pull request state',
                },
                per_page: {
                  type: 'number',
                  minimum: 1,
                  maximum: 100,
                  description: 'Number of results per page',
                },
              },
              required: ['owner', 'repo'],
            },
          },
          {
            name: 'get_file_contents',
            description: 'Get the contents of a file from a repository',
            inputSchema: {
              type: 'object',
              properties: {
                owner: {
                  type: 'string',
                  description: 'Repository owner',
                },
                repo: {
                  type: 'string',
                  description: 'Repository name',
                },
                path: {
                  type: 'string',
                  description: 'File path',
                },
                ref: {
                  type: 'string',
                  description: 'Branch, tag, or commit SHA',
                },
              },
              required: ['owner', 'repo', 'path'],
            },
          },
        ],
      };
    });

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;

      try {
        switch (name) {
          case 'search_repositories':
            return await this.searchRepositories(args as any);
          case 'get_repository':
            return await this.getRepository(args as any);
          case 'list_issues':
            return await this.listIssues(args as any);
          case 'create_issue':
            return await this.createIssue(args as any);
          case 'list_pull_requests':
            return await this.listPullRequests(args as any);
          case 'get_file_contents':
            return await this.getFileContents(args as any);
          default:
            throw new Error(`Unknown tool: ${name}`);
        }
      } catch (error) {
        return {
          content: [
            {
              type: 'text',
              text: `Error: ${error instanceof Error ? error.message : String(error)}`,
            },
          ],
        };
      }
    });
  }

  private async searchRepositories(args: {
    query: string;
    sort?: string;
    order?: string;
    per_page?: number;
  }) {
    const { data } = await this.octokit.search.repos({
      q: args.query,
      sort: args.sort as any,
      order: args.order as any,
      per_page: args.per_page || 10,
    });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              total_count: data.total_count,
              repositories: data.items.map((repo) => ({
                name: repo.name,
                full_name: repo.full_name,
                description: repo.description,
                html_url: repo.html_url,
                stars: repo.stargazers_count,
                forks: repo.forks_count,
                language: repo.language,
                updated_at: repo.updated_at,
              })),
            },
            null,
            2
          ),
        },
      ],
    };
  }

  private async getRepository(args: { owner: string; repo: string }) {
    const { data } = await this.octokit.repos.get({
      owner: args.owner,
      repo: args.repo,
    });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              name: data.name,
              full_name: data.full_name,
              description: data.description,
              html_url: data.html_url,
              clone_url: data.clone_url,
              stars: data.stargazers_count,
              forks: data.forks_count,
              language: data.language,
              created_at: data.created_at,
              updated_at: data.updated_at,
              default_branch: data.default_branch,
              topics: data.topics,
            },
            null,
            2
          ),
        },
      ],
    };
  }

  private async listIssues(args: {
    owner: string;
    repo: string;
    state?: string;
    labels?: string;
    per_page?: number;
  }) {
    const { data } = await this.octokit.issues.listForRepo({
      owner: args.owner,
      repo: args.repo,
      state: (args.state as any) || 'open',
      labels: args.labels,
      per_page: args.per_page || 10,
    });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              issues: data.map((issue) => ({
                number: issue.number,
                title: issue.title,
                body: issue.body,
                state: issue.state,
                html_url: issue.html_url,
                labels: issue.labels.map((label) => ({
                  name: label.name,
                  color: label.color,
                })),
                assignees: issue.assignees.map((assignee) => ({
                  login: assignee.login,
                  html_url: assignee.html_url,
                })),
                created_at: issue.created_at,
                updated_at: issue.updated_at,
              })),
            },
            null,
            2
          ),
        },
      ],
    };
  }

  private async createIssue(args: {
    owner: string;
    repo: string;
    title: string;
    body?: string;
    labels?: string[];
    assignees?: string[];
  }) {
    const { data } = await this.octokit.issues.create({
      owner: args.owner,
      repo: args.repo,
      title: args.title,
      body: args.body,
      labels: args.labels,
      assignees: args.assignees,
    });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              number: data.number,
              title: data.title,
              body: data.body,
              state: data.state,
              html_url: data.html_url,
              labels: data.labels.map((label) => ({
                name: label.name,
                color: label.color,
              })),
              assignees: data.assignees.map((assignee) => ({
                login: assignee.login,
                html_url: assignee.html_url,
              })),
              created_at: data.created_at,
            },
            null,
            2
          ),
        },
      ],
    };
  }

  private async listPullRequests(args: {
    owner: string;
    repo: string;
    state?: string;
    per_page?: number;
  }) {
    const { data } = await this.octokit.pulls.list({
      owner: args.owner,
      repo: args.repo,
      state: (args.state as any) || 'open',
      per_page: args.per_page || 10,
    });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              pull_requests: data.map((pr) => ({
                number: pr.number,
                title: pr.title,
                body: pr.body,
                state: pr.state,
                html_url: pr.html_url,
                head: {
                  ref: pr.head.ref,
                  sha: pr.head.sha,
                },
                base: {
                  ref: pr.base.ref,
                  sha: pr.base.sha,
                },
                user: {
                  login: pr.user?.login,
                  html_url: pr.user?.html_url,
                },
                created_at: pr.created_at,
                updated_at: pr.updated_at,
              })),
            },
            null,
            2
          ),
        },
      ],
    };
  }

  private async getFileContents(args: {
    owner: string;
    repo: string;
    path: string;
    ref?: string;
  }) {
    const { data } = await this.octokit.repos.getContent({
      owner: args.owner,
      repo: args.repo,
      path: args.path,
      ref: args.ref,
    });

    if (Array.isArray(data)) {
      // Directory listing
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(
              {
                type: 'directory',
                path: args.path,
                contents: data.map((item) => ({
                  name: item.name,
                  type: item.type,
                  path: item.path,
                  size: item.size,
                  download_url: item.download_url,
                })),
              },
              null,
              2
            ),
          },
        ],
      };
    } else {
      // File content
      const content = Buffer.from(data.content, 'base64').toString('utf-8');
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(
              {
                type: 'file',
                name: data.name,
                path: data.path,
                size: data.size,
                content: content,
                encoding: data.encoding,
                download_url: data.download_url,
              },
              null,
              2
            ),
          },
        ],
      };
    }
  }

  async run(): Promise<void> {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error('GitHub MCP server running on stdio');
  }
}

// Start the server
const server = new GitHubMCPServer();
server.run().catch((error) => {
  console.error('Failed to start GitHub MCP server:', error);
  process.exit(1);
});
