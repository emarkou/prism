DASHBOARD_QUERY = """
query DashboardQuery($contribFrom: DateTime!, $reviewSearch: String!, $prFirst: Int!, $inboxFirst: Int!) {
  viewer {
    login
    name
    pullRequests(first: $prFirst, states: [OPEN], orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes {
        number
        title
        url
        isDraft
        mergeable
        createdAt
        updatedAt
        reviewDecision
        reviews(first: 10) {
          totalCount
        }
        repository {
          nameWithOwner
        }
        statusCheckRollup {
          state
          contexts(first: 20) {
            nodes {
              ... on CheckRun {
                name
                status
                conclusion
              }
              ... on StatusContext {
                context
                state
              }
            }
          }
        }
      }
    }
    contributionsCollection(from: $contribFrom) {
      contributionCalendar {
        totalContributions
        weeks {
          firstDay
          contributionDays {
            date
            contributionCount
          }
        }
      }
      totalCommitContributions
      totalPullRequestReviewContributions
      commitContributionsByRepository(maxRepositories: 10) {
        repository {
          nameWithOwner
        }
        contributions {
          totalCount
        }
      }
    }
  }
  reviewRequested: search(query: $reviewSearch, type: ISSUE, first: $inboxFirst) {
    nodes {
      ... on PullRequest {
        number
        title
        url
        updatedAt
        repository {
          nameWithOwner
        }
        isDraft
        mergeable
        reviewDecision
        reviews(first: 5) {
          totalCount
        }
        statusCheckRollup {
          state
          contexts(first: 20) {
            nodes {
              ... on CheckRun {
                name
                status
                conclusion
              }
              ... on StatusContext {
                context
                state
              }
            }
          }
        }
      }
    }
  }
  rateLimit {
    remaining
    resetAt
  }
}
"""

TOGGLE_DRAFT_MUTATION = """
mutation ConvertPRToDraft($prId: ID!) {
  convertPullRequestToDraft(input: {pullRequestId: $prId}) {
    pullRequest {
      isDraft
      id
    }
  }
}
"""

MARK_READY_MUTATION = """
mutation MarkPRReady($prId: ID!) {
  markPullRequestReadyForReview(input: {pullRequestId: $prId}) {
    pullRequest {
      isDraft
      id
    }
  }
}
"""

PR_NODE_ID_QUERY = """
query GetPRNodeId($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      id
      isDraft
    }
  }
}
"""
