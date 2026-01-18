import { Body, Container, Head, Hr, Html, Text } from '@react-email/components'

interface WelcomeEmailProps {
  organizationName: string
  userName: string
}

export default function WelcomeEmail({ organizationName, userName }: WelcomeEmailProps) {
  return (
    <Html>
      <Head />
      <Body style={main}>
        <Container style={container}>
          <Text style={heading}>Welcome to Tango!</Text>
          <Text style={text}>Hi {userName},</Text>
          <Text style={text}>
            You've successfully joined <strong>{organizationName}</strong>.
          </Text>
          <Hr style={hr} />
          <Text style={footer}>The Tango Team</Text>
        </Container>
      </Body>
    </Html>
  )
}

// Styles
const main = {
  backgroundColor: '#f6f9fc',
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
}

const container = {
  backgroundColor: '#ffffff',
  margin: '0 auto',
  padding: '40px 20px',
  maxWidth: '560px',
}

const heading = {
  fontSize: '24px',
  fontWeight: '600',
  color: '#1a1a1a',
  margin: '0 0 20px',
}

const text = {
  fontSize: '16px',
  color: '#4a4a4a',
  lineHeight: '24px',
  margin: '0 0 16px',
}

const hr = {
  borderColor: '#e6e6e6',
  margin: '30px 0',
}

const footer = {
  fontSize: '14px',
  color: '#9ca3af',
  margin: '0',
}

// Preview props for development
WelcomeEmail.PreviewProps = {
  organizationName: 'Acme Corp',
  userName: 'Jane',
} satisfies WelcomeEmailProps
