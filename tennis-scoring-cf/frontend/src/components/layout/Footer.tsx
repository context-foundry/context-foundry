import React from 'react';

export function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="bg-gray-50 border-t border-gray-200 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* About */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">
              Tennis Scoring App
            </h3>
            <p className="text-sm text-gray-600">
              Real-time tennis match scoring for high school tennis teams.
              Track scores, view live matches, and manage your team.
            </p>
          </div>

          {/* Quick Links */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">
              Quick Links
            </h3>
            <ul className="space-y-2 text-sm text-gray-600">
              <li>
                <a href="/" className="hover:text-blue-600 transition-colors">
                  All Matches
                </a>
              </li>
              <li>
                <a href="/dashboard" className="hover:text-blue-600 transition-colors">
                  Dashboard
                </a>
              </li>
              <li>
                <a href="/matches/create" className="hover:text-blue-600 transition-colors">
                  Create Match
                </a>
              </li>
            </ul>
          </div>

          {/* Contact */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">
              Support
            </h3>
            <p className="text-sm text-gray-600">
              Need help? Contact your coach or system administrator.
            </p>
          </div>
        </div>

        <div className="mt-8 pt-8 border-t border-gray-200">
          <p className="text-center text-sm text-gray-500">
            {currentYear} Tennis Scoring App. Built for high school tennis teams.
          </p>
        </div>
      </div>
    </footer>
  );
}
