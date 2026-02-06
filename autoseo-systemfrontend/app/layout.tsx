export const metadata = {
  title: 'AutoSEO - Dashboard',
  description: 'AI-powered website generation',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}