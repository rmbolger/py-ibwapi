"""Contains custom exceptions for ibwapi."""


class WAPIError(Exception):
    """Custom exception to handle WAPI errors."""

    def __init__(self, response):
        try:
            err = response.json()
            error_message = err.get('Error', 'Unknown error')
            error_code = err.get('code', None)
            error_text = err.get('text', None)
        except ValueError:
            # If response is not JSON, use a generic error message
            error_message = 'Unknown error (non-JSON response)'
            error_code = err.response.status_code
            error_text = err.response.text

        self.status_code = response.status_code
        self.error_message = error_message
        self.error_code = error_code
        self.error_text = error_text

        super().__init__(f'{self.status_code}: {self.error_message}')


class LimitExceededError(Exception):
    """Raised when the result set exceeds the specified max_results limit."""

    def __init__(self, max_results, actual_results):
        super().__init__(
            f'Result set of {actual_results} exceeds the max_results limit of {max_results}.'
        )
