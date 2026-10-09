"""Lossless, JSON-only checkpoints; never unpickle database content."""
from dataclasses import asdict, fields
from datetime import datetime
from .models import (SourceCandidate, SharedEventCandidate, DiscoveryLaneResult, DiscoveryUsage,
 PhaseBResult, PhaseCResult, ProfileEventAnalysis, AnalysisUsage)


def json_value(value):
    if isinstance(value,datetime): return value.isoformat()
    if isinstance(value,set): return sorted(value)
    if isinstance(value,dict): return {k:json_value(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [json_value(v) for v in value]
    return value


def encode(value): return json_value(asdict(value))


def source(value):
    value=dict(value)
    for k in ('published_at','retrieved_at'):
        if value.get(k):value[k]=datetime.fromisoformat(value[k])
    value['routed_profiles']=set(value.get('routed_profiles',[]))
    return SourceCandidate(**value)


def phase_b(value):
    value=dict(value);value['as_of']=datetime.fromisoformat(value['as_of'])
    value['candidates']=[source(r) for r in value['candidates']]
    events=[]
    for row in value['events']:
        row=dict(row);row['candidates']=[source(r) for r in row['candidates']];row['routed_profiles']=set(row['routed_profiles'])
        for k in ('first_seen_at','last_seen_at'):
            if row.get(k): row[k]=datetime.fromisoformat(row[k])
        events.append(SharedEventCandidate(**row))
    value['events']=events
    lanes=[]
    for row in value['discovery_lanes']:
        row=dict(row);row['candidates']=[source(r) for r in row['candidates']];row['usage']=DiscoveryUsage(**row['usage']);lanes.append(DiscoveryLaneResult(**row))
    value['discovery_lanes']=lanes
    return PhaseBResult(**value)


def phase_c(value):
    return PhaseCResult(analyses=[ProfileEventAnalysis(**r) for r in value['analyses']],eligible_analyses=[ProfileEventAnalysis(**r) for r in value.get('eligible_analyses',[])],
      usage_by_profile={k:AnalysisUsage(**r) for k,r in value['usage_by_profile'].items()},omitted_by_profile=value['omitted_by_profile'])
