import Link from 'next/link';
import { ArrowRight, BookOpen, Target, Trophy, Zap } from 'lucide-react';

export default function HomePage() {
  const features = [
    {
      icon: BookOpen,
      title: '169 Expert Patterns',
      description: 'Comprehensive library of Workday best practices and expertise patterns',
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
    },
    {
      icon: Target,
      title: 'Interactive Learning',
      description: 'Quizzes, scenarios, and exercises to reinforce your knowledge',
      color: 'text-green-600',
      bgColor: 'bg-green-50',
    },
    {
      icon: Zap,
      title: 'AI-Powered Hints',
      description: 'Get intelligent hints and explanations when you need help',
      color: 'text-purple-600',
      bgColor: 'bg-purple-50',
    },
    {
      icon: Trophy,
      title: 'Track Progress',
      description: 'Earn achievements and certificates as you master patterns',
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-50',
    },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      {/* Hero Section */}
      <section className="text-center mb-16">
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-gray-900 mb-6">
          Master Workday
          <span className="block text-blue-600 mt-2">Best Practices</span>
        </h1>
        <p className="text-xl text-gray-600 max-w-3xl mx-auto mb-8">
          Learn from 169 expert patterns through interactive quizzes, real-world scenarios,
          and hands-on exercises. Track your progress and earn certificates.
        </p>

        {/* CTA Buttons */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link
            href="/patterns"
            className="inline-flex items-center gap-2 px-8 py-4 text-lg font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 shadow-lg hover:shadow-xl transition-all min-h-[44px]"
            aria-label="Start learning"
          >
            Start Learning
            <ArrowRight className="h-5 w-5" aria-hidden="true" />
          </Link>
          <Link
            href="/progress"
            className="inline-flex items-center gap-2 px-8 py-4 text-lg font-semibold text-blue-600 bg-white border-2 border-blue-600 rounded-lg hover:bg-blue-50 transition-all min-h-[44px]"
            aria-label="View your progress"
          >
            <Trophy className="h-5 w-5" aria-hidden="true" />
            View Progress
          </Link>
        </div>
      </section>

      {/* Stats Section */}
      <section className="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-16">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 text-center">
          <div className="text-4xl font-bold text-blue-600 mb-2">169</div>
          <div className="text-gray-600">Expert Patterns</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 text-center">
          <div className="text-4xl font-bold text-green-600 mb-2">3</div>
          <div className="text-gray-600">Learning Modes</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 text-center">
          <div className="text-4xl font-bold text-purple-600 mb-2">5</div>
          <div className="text-gray-600">Achievement Tiers</div>
        </div>
      </section>

      {/* Features Section */}
      <section className="mb-16">
        <h2 className="text-3xl font-bold text-gray-900 text-center mb-12">
          Everything You Need to Excel
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {features.map((feature) => {
            const Icon = feature.icon;
            return (
              <div
                key={feature.title}
                className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow"
              >
                <div className="flex items-start gap-4">
                  <div className={`p-3 rounded-lg ${feature.bgColor}`}>
                    <Icon className={`h-6 w-6 ${feature.color}`} aria-hidden="true" />
                  </div>
                  <div>
                    <h3 className="text-xl font-semibold text-gray-900 mb-2">
                      {feature.title}
                    </h3>
                    <p className="text-gray-600 leading-relaxed">
                      {feature.description}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* How It Works */}
      <section className="bg-gradient-to-br from-blue-50 to-purple-50 rounded-2xl p-8 md:p-12">
        <h2 className="text-3xl font-bold text-gray-900 text-center mb-8">
          How It Works
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="text-center">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-blue-600 text-white rounded-full font-bold text-xl mb-4">
              1
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Browse Patterns
            </h3>
            <p className="text-gray-600">
              Explore our library of 169 Workday best practices organized by category
            </p>
          </div>

          <div className="text-center">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-green-600 text-white rounded-full font-bold text-xl mb-4">
              2
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Learn Interactively
            </h3>
            <p className="text-gray-600">
              Complete quizzes, scenarios, and fill-in-the-blank exercises
            </p>
          </div>

          <div className="text-center">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-purple-600 text-white rounded-full font-bold text-xl mb-4">
              3
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Earn Achievements
            </h3>
            <p className="text-gray-600">
              Track progress, unlock badges, and download certificates
            </p>
          </div>
        </div>

        <div className="text-center mt-8">
          <Link
            href="/patterns"
            className="inline-flex items-center gap-2 px-6 py-3 text-base font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 shadow-lg hover:shadow-xl transition-all min-h-[44px]"
            aria-label="Get started now"
          >
            Get Started Now
            <ArrowRight className="h-5 w-5" aria-hidden="true" />
          </Link>
        </div>
      </section>
    </div>
  );
}
