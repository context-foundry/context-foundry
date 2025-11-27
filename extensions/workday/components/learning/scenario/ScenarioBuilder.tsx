'use client';

import React, { useReducer, useEffect } from 'react';
import { Scenario, ScenarioState, ScenarioNode } from '@/types/learning';
import { DecisionPoint } from './DecisionPoint';
import { OutcomeDisplay } from './OutcomeDisplay';
import { ProgressBar } from '../shared/ProgressBar';
import { MapPin } from 'lucide-react';

interface ScenarioBuilderProps {
  scenario: Scenario;
  onComplete: (result: {
    successful: boolean;
    decisionsCorrect: number;
    decisionsTotal: number;
    timeTaken: number;
  }) => void;
}

type ScenarioAction =
  | { type: 'SELECT_OPTION'; nextNodeId: string; isCorrect: boolean }
  | { type: 'COMPLETE_SCENARIO'; successful: boolean }
  | { type: 'RESTART_SCENARIO' };

function createInitialState(scenario: Scenario): ScenarioState {
  return {
    currentNodeId: scenario.startNodeId,
    pathTaken: [scenario.startNodeId],
    decisionsCorrect: 0,
    decisionsTotal: 0,
    completed: false,
    successful: null,
    startedAt: Date.now(),
    completedAt: null,
  };
}

function scenarioReducer(state: ScenarioState, action: ScenarioAction): ScenarioState {
  switch (action.type) {
    case 'SELECT_OPTION':
      return {
        ...state,
        currentNodeId: action.nextNodeId,
        pathTaken: [...state.pathTaken, action.nextNodeId],
        decisionsCorrect: action.isCorrect
          ? state.decisionsCorrect + 1
          : state.decisionsCorrect,
        decisionsTotal: state.decisionsTotal + 1,
      };

    case 'COMPLETE_SCENARIO':
      return {
        ...state,
        completed: true,
        successful: action.successful,
        completedAt: Date.now(),
      };

    case 'RESTART_SCENARIO':
      return {
        ...state,
        currentNodeId: state.pathTaken[0],
        pathTaken: [state.pathTaken[0]],
        decisionsCorrect: 0,
        decisionsTotal: 0,
        completed: false,
        successful: null,
        startedAt: Date.now(),
        completedAt: null,
      };

    default:
      return state;
  }
}

export function ScenarioBuilder({ scenario, onComplete }: ScenarioBuilderProps) {
  const [state, dispatch] = useReducer(
    scenarioReducer,
    scenario,
    createInitialState
  );

  const currentNode = scenario.nodes.find((n) => n.id === state.currentNodeId);

  // Calculate progress based on decisions made
  const estimatedTotalDecisions = scenario.nodes.filter((n) => n.type === 'decision').length;
  const progress = estimatedTotalDecisions > 0
    ? Math.min((state.decisionsTotal / estimatedTotalDecisions) * 100, 100)
    : 0;

  // Handle scenario completion
  useEffect(() => {
    if (state.completed && state.completedAt && state.successful !== null) {
      const timeTaken = Math.round((state.completedAt - state.startedAt) / 1000);

      onComplete({
        successful: state.successful,
        decisionsCorrect: state.decisionsCorrect,
        decisionsTotal: state.decisionsTotal,
        timeTaken,
      });
    }
  }, [state.completed, state.completedAt, state.successful, state.decisionsCorrect, state.decisionsTotal, state.startedAt, onComplete]);

  if (!currentNode) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">Error: Invalid scenario state</p>
      </div>
    );
  }

  const handleSelectOption = (nextNodeId: string, isCorrect: boolean = false) => {
    const nextNode = scenario.nodes.find((n) => n.id === nextNodeId);

    dispatch({ type: 'SELECT_OPTION', nextNodeId, isCorrect });

    // Check if we reached an end node
    if (nextNode && nextNode.type === 'end') {
      dispatch({
        type: 'COMPLETE_SCENARIO',
        successful: nextNode.isSuccessful ?? false,
      });
    }
  };

  const handleRestart = () => {
    dispatch({ type: 'RESTART_SCENARIO' });
  };

  // Show outcome display for outcome and end nodes
  if (currentNode.type === 'outcome' || currentNode.type === 'end') {
    return (
      <OutcomeDisplay
        node={currentNode}
        isCompleted={state.completed}
        decisionsCorrect={state.decisionsCorrect}
        decisionsTotal={state.decisionsTotal}
        onContinue={
          currentNode.type === 'outcome' && currentNode.options && currentNode.options.length > 0
            ? () => handleSelectOption(currentNode.options![0].nextNodeId, currentNode.options![0].isCorrect)
            : undefined
        }
        onRestart={state.completed ? handleRestart : undefined}
      />
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Progress Header */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <MapPin className="h-5 w-5 text-blue-600" aria-hidden="true" />
            <span className="text-sm font-medium text-gray-700">
              Scenario Progress
            </span>
          </div>
          <span className="text-sm text-gray-600">
            {state.decisionsTotal} {state.decisionsTotal === 1 ? 'decision' : 'decisions'} made
          </span>
        </div>
        <ProgressBar value={progress} className="h-2" />
      </div>

      {/* Current Node Content */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        {/* Title */}
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            {currentNode.title}
          </h2>
          {currentNode.type === 'start' && (
            <span className="inline-block px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm font-medium">
              Start
            </span>
          )}
        </div>

        {/* Description */}
        <div className="mb-6">
          <p className="text-gray-700 leading-relaxed whitespace-pre-line">
            {currentNode.description}
          </p>
        </div>

        {/* Image (if available) */}
        {currentNode.imageUrl && (
          <div className="mb-6 rounded-lg overflow-hidden border border-gray-200">
            <img
              src={currentNode.imageUrl}
              alt="Scenario illustration"
              className="w-full h-auto"
            />
          </div>
        )}

        {/* Decision Point */}
        {(currentNode.type === 'decision' || currentNode.type === 'start') &&
          currentNode.options && (
            <DecisionPoint
              options={currentNode.options}
              onSelectOption={handleSelectOption}
            />
          )}
      </div>

      {/* Path Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <span>Path:</span>
        {state.pathTaken.map((nodeId, index) => {
          const node = scenario.nodes.find((n) => n.id === nodeId);
          return (
            <React.Fragment key={nodeId}>
              {index > 0 && <span>→</span>}
              <span className="font-medium">{node?.title || nodeId}</span>
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
