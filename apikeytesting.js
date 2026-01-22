const testAPI = async () => {
  try {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': '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',
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514',
        max_tokens: 1024,
        messages: [
          { role: 'user', content: 'Hello' }
        ]
      })
    });

    if (!response.ok) {
      const errorData = await response.json();
      console.error('API Error:', response.status, errorData);
    } else {
      const data = await response.json();
      console.log('Success:', data);
    }
  } catch (error) {
    console.error('Request failed:', error);
  }
};

// Call the function
testAPI();