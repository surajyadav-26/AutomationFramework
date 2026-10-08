@api
Feature: User authentication API
  The auth endpoint exchanges credentials for an access token.

  @smoke
  Scenario: Valid credentials return a token
    When I request a token with valid credentials
    Then the response status is 200
    And the response body matches the user schema
    And the response contains an access token

  Scenario: Wrong password is rejected
    When I request a token with a wrong password
    Then the response status is 400
    And the response message is "Invalid credentials"
