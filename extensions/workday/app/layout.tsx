import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { ProgressProvider } from '@/lib/progress/progress-store';
import Link from 'next/link';
import { BookOpen, TrendingUp, Home } from 'lucide-react';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'WorkWise - Workday Expertise Platform',
  description: 'Master Workday best practices through interactive learning',
  keywords: ['Workday', 'learning', 'training', 'best practices', 'expertise'],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <ProgressProvider>
          <div className="min-h-screen flex flex-col">
            {/* Header */}
            <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
              <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex items-center justify-between h-16">
                  {/* Logo */}
                  <Link
                    href="/"
                    className="flex items-center gap-2 text-xl font-bold text-blue-600 hover:text-blue-700 min-h-[44px]"
                    aria-label="WorkWise Home"
                  >
                    <BookOpen className="h-6 w-6" aria-hidden="true" />
                    WorkWise
                  </Link>

                  {/* Navigation */}
                  <div className="flex items-center gap-1">
                    <Link
                      href="/"
                      className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors min-h-[44px]"
                      aria-label="Home"
                    >
                      <Home className="h-4 w-4" aria-hidden="true" />
                      <span className="hidden sm:inline">Home</span>
                    </Link>
                    <Link
                      href="/patterns"
                      className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors min-h-[44px]"
                      aria-label="Browse Patterns"
                    >
                      <BookOpen className="h-4 w-4" aria-hidden="true" />
                      <span className="hidden sm:inline">Patterns</span>
                    </Link>
                    <Link
                      href="/progress"
                      className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors min-h-[44px]"
                      aria-label="Your Progress"
                    >
                      <TrendingUp className="h-4 w-4" aria-hidden="true" />
                      <span className="hidden sm:inline">Progress</span>
                    </Link>
                  </div>
                </div>
              </nav>
            </header>

            {/* Main Content */}
            <main className="flex-1 bg-gray-50">
              {children}
            </main>

            {/* Footer */}
            <footer className="bg-white border-t border-gray-200 mt-auto">
              <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <div className="text-center">
                  <p className="text-sm text-gray-600">
                    &copy; {new Date().getFullYear()} WorkWise. All rights reserved.
                  </p>
                  <p className="text-xs text-gray-500 mt-2">
                    Workday Expertise Platform - Master best practices through interactive learning
                  </p>
                </div>
              </div>
            </footer>
          </div>
        </ProgressProvider>
      </body>
    </html>
  );
}
