import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { AuthProvider } from '@/contexts/AuthContext';
import { WebSocketProvider } from '@/contexts/WebSocketContext';
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Tennis Scoring App',
  description: 'Real-time tennis match scoring for high school tennis teams',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <AuthProvider>
          <WebSocketProvider>
            <div className="flex flex-col min-h-screen">
              <Header />
              <main className="flex-1 bg-gray-50">{children}</main>
              <Footer />
            </div>
          </WebSocketProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
