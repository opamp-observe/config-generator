# MongoDB monitoring queries: performance, slow operations, locks and internal logs

## Scope and interpretation

Scope: MongoDB Server 6.0, 7.0 and 8.0 release families, using mongosh. Legacy versions are included for installed-estate compatibility; inclusion does not imply current support. Later rapid releases and 9.0 are outside this matrix.

MongoDB-compatible services, including Amazon DocumentDB and Azure Cosmos DB, need to be validated.

These are operational patterns assembled from vendor documentation. Query identifiers are local to this document. Thresholds and schedules are suggested starting points, not vendor defaults. Documentation review was performed; queries were not executed against database servers.

## What can be retrieved entirely through a database connection?

| Requirement | Recommended interface | Limitation |
| --- | --- | --- |
| Slow operations running now | $currentOp | Operations between samples are missed. |
| Transactions and lock contention | $currentOp, serverStatus | Does not expose a general SQL-style waiter-to-blocker graph. |
| Completed slow operations | Each database's system.profile | Profiling must already be enabled; capped retention. |
| Query-pattern summaries | Aggregate retained profiler records; optional $queryStats | Profiler summaries reflect selected records, not all traffic. |
| Internal errors and warnings | getLog global buffer | Recent RAM events only; not a complete logfile reader. |
| Storage, index usage and latency | dbStats, $collStats, $indexStats, serverStatus | Node scope and counter resets matter. |
| Replication health | replSetGetStatus and local oplog | Replica-set member access, not mongos. |

“Internal logs” means information accessible over an authenticated database connection without publishing files or forwarding logs to an external service. This does not provide unlimited historical retention. Profiler records live in database collections; getLog reads a bounded memory buffer.

## Prerequisites and collection rules

Use a dedicated monitoring principal. The built-in clusterMonitor role is a starting point for cluster diagnostics; inspect its exact privileges for your release and deployment. Reading application database system.profile requires explicit find access to that system collection; ordinary read access should not be assumed sufficient. Changes to profiler settings need enableProfiler, separate from collection. Q20 needs queryStatsRead. Avoid granting root or clusterAdmin merely to collect metrics. [Built-in roles](https://www.mongodb.com/docs/manual/reference/built-in-roles/?deployment-type=self).

Connect to admin for $currentOp and administrative commands. Replace appdb and orders throughout with the actual database and collection. Each snippet is independently runnable in mongosh. Examples use var where a value is needed, so repeated execution in one shell does not redeclare const bindings.

Node-level counters are not cluster totals. Collect each relevant mongod member and router with deployment ID, host, role, server version, uptime and UTC sample time. On mongos, $currentOp with localOps:false reports shard operations; use localOps:true for that router. Replication and WiredTiger queries need a data-bearing mongod. Managed-service tiers can restrict commands even when the server version matches.

Compute rates from successive samples: delta(counter) / elapsed seconds. Discard intervals crossing restart, role changes, reset or a counter decrease. Retain BSON integer precision in the collector; converting every NumberLong to JavaScript Number can lose precision. Separate gauges such as active connections from counters such as totalCreated.

Bound query windows and result counts. Profiler sorting/aggregation can scan the capped collection and needs lower polling frequency than simple gauges. Text, client addresses, command literals and logs may contain sensitive data; restrict their readers and retention. Nothing here enables auditing or guarantees a complete record of failed requests.

## Compatibility matrix

Y = documented common interface; P = profiler data already collected on the target mongod/database; R = replica-set data-bearing member; W = WiredTiger node; A = optional Atlas queryStats path, subject to eligibility; — = not claimed. Version compatibility is documentation-based, not a runtime certification. Missing fields must be handled, not converted to zero.

| Query name | 6.0 | 7.0 | 8.0 |
| --- | --- | --- | --- |
| Q01 Environment and configuration | Y | Y | Y |
| Q02 Active slow operations | Y | Y | Y |
| Q03 Long and idle transactions | Y | Y | Y |
| Q04 Activity by application | Y | Y | Y |
| Q05 Operations waiting for locks | Y | Y | Y |
| Q06 Lock counters and contention | Y | Y | Y |
| Q07 Recent slow executions | P | P | P |
| Q08 Expensive recorded query patterns | P | P | P |
| Q09 Profiler collection health | P | P | P |
| Q10 Workload and connection counters | Y | Y | Y |
| Q11 Database storage totals | Y | Y | Y |
| Q12 Index usage | Y | Y | Y |
| Q13 WiredTiger cache pressure | W | W | W |
| Q14 Current maintenance operations | Y | Y | Y |
| Q15 Durability and journal counters | W | W | W |
| Q16 Collection latency counters | Y | Y | Y |
| Q17 Plan cache inspection | Y | Y | Y |
| Q18 Replica health and apply lag | R | R | R |
| Q19 Oplog retention window | R | R | R |
| Q20 Optional query statistics | A (6.0.7+) | A (7.0.12+) | A |
| Q21 Recent internal errors and warnings | Y | Y | Y |
| Q22 Recent slow-operation log entries | Y | Y | Y |

The Q20 marker does not mean every 7.0 deployment supports queryStats: the 7.0 documentation identifies introduction in 7.0.12 and availability starting in 6.0.7, and the cited 8.0 interface documents Atlas M10+ eligibility. Do not enable internal server parameters to make this work on unsupported deployments. Its output is explicitly unstable, so Q20 deliberately returns raw records instead of depending on metric paths. Later releases alter the schema.

Version baselines: [6.0 currentOp](https://www.mongodb.com/docs/v6.0/reference/operator/aggregation/currentOp/), [7.0 currentOp](https://www.mongodb.com/docs/v7.0/reference/operator/aggregation/currentop/), [8.0 currentOp](https://www.mongodb.com/docs/v8.0/reference/operator/aggregation/currentop/); [6.0 serverStatus](https://www.mongodb.com/docs/v6.0/reference/command/serverStatus/), [7.0 serverStatus](https://www.mongodb.com/docs/v7.0/reference/command/serverstatus/), [8.0 serverStatus](https://www.mongodb.com/docs/v8.0/reference/command/serverstatus/); [7.0 queryStats](https://www.mongodb.com/docs/v7.0/reference/operator/aggregation/queryStats/), [8.0 queryStats](https://www.mongodb.com/docs/v8.0/reference/operator/aggregation/querystats/). The legacy currentOp command is deprecated from 6.2; these examples use the aggregation stage.

## Query catalogue

### Q01 — Environment and configuration

Run on each monitored process. Configuration access can be separately restricted.

~~~javascript
db.adminCommand({buildInfo:1});
db.adminCommand({hello:1});
db.adminCommand({getCmdLineOpts:1});
~~~

Record version, process identity and topology. getCmdLineOpts can reveal paths and deployment details; select only required fields before exporting.

Sources: [getCmdLineOpts](https://www.mongodb.com/docs/v8.0/reference/command/getcmdlineopts/).

### Q02 — Active slow operations

Example threshold: active for at least five seconds.

~~~javascript
db.getSiblingDB("admin").aggregate([
  {$currentOp:{allUsers:true,localOps:false}},
  {$match:{active:true,secs_running:{$gte:5}}},
  {$project:{host:1,shard:1,opid:1,op:1,ns:1,secs_running:1,
    appName:1,client:1,waitingForLock:1,command:1}},
  {$sort:{secs_running:-1}}, {$limit:50}
],{maxTimeMS:5000});
~~~

Elapsed time includes waiting; it is not CPU time. Queryable Encryption may redact the command and associated diagnostics.

Sources: [$currentOp](https://www.mongodb.com/docs/v8.0/reference/operator/aggregation/currentop/).

### Q03 — Long and idle transactions

Include inactive sessions that may retain transaction resources.

~~~javascript
db.getSiblingDB("admin").aggregate([
  {$currentOp:{allUsers:true,idleSessions:true}},
  {$match:{transaction:{$exists:true}}},
  {$project:{host:1,opid:1,type:1,active:1,lsid:1,
    transaction:1,waitingForLock:1,locks:1}},
  {$limit:100}
],{maxTimeMS:5000});
~~~

Inspect transaction timeOpenMicros/timeInactiveMicros where present. An idle connection alone does not prove an open transaction.

Sources: [$currentOp](https://www.mongodb.com/docs/v8.0/reference/operator/aggregation/currentop/).

### Q04 — Activity by application

Count currently active operations by application and operation type.

~~~javascript
db.getSiblingDB("admin").aggregate([
  {$currentOp:{allUsers:true}},
  {$match:{active:true}},
  {$group:{_id:{app:"$appName",op:"$op"},operations:{$sum:1}}},
  {$sort:{operations:-1}}, {$limit:50}
],{maxTimeMS:5000});
~~~

This is an instantaneous concurrency sample, not requests per second. Set appName in application connection strings to make it useful.

Sources: [$currentOp](https://www.mongodb.com/docs/v8.0/reference/operator/aggregation/currentop/), [serverStatus](https://www.mongodb.com/docs/v8.0/reference/command/serverstatus/).

### Q05 — Operations waiting for locks

Run during blocking symptoms.

~~~javascript
db.getSiblingDB("admin").aggregate([
  {$currentOp:{allUsers:true,idleSessions:true}},
  {$match:{waitingForLock:true}},
  {$project:{host:1,opid:1,ns:1,secs_running:1,
    command:1,locks:1,lockStats:1,lsid:1,transaction:1}},
  {$limit:100}
],{maxTimeMS:5000});
~~~

Use alongside Q03 to investigate possible lock holders. Similar namespace or locks fields are not proof of a blocker relationship; do not automatically kill a guessed blocker.

Sources: [$currentOp](https://www.mongodb.com/docs/v8.0/reference/operator/aggregation/currentop/).

### Q06 — Lock counters and contention

Sample local lock acquisition/wait counters.

~~~javascript
var s = db.adminCommand({serverStatus:1});
printjson({host:s.host,localTime:s.localTime,uptime:s.uptime,locks:s.locks});
~~~

Use deltas in acquireWaitCount and timeAcquiringMicros by resource/mode. Storage-engine write conflicts and flow control are separate contention mechanisms.

Sources: [serverStatus](https://www.mongodb.com/docs/v8.0/reference/command/serverstatus/).

### Q07 — Recent slow executions

Read the last hour of retained profiler records taking at least 500 ms.

~~~javascript
db.getSiblingDB("appdb").system.profile.find(
  {ts:{$gte:new Date(Date.now()-3600000)},millis:{$gte:500}},
  {ts:1,op:1,ns:1,millis:1,planSummary:1,docsExamined:1,
    keysExamined:1,nreturned:1,command:1}
).sort({ts:-1}).limit(100).maxTimeMS(5000);
~~~

Captured records only. millis is a duration in milliseconds; it is not interchangeable with newer working-time fields or the exact slow-log selection criterion.

Sources: [Profiler output](https://www.mongodb.com/docs/v8.0/reference/database-profiler/).

### Q08 — Expensive recorded query patterns

Rank selected profiler records by cumulative elapsed time.

~~~javascript
db.getSiblingDB("appdb").system.profile.aggregate([
  {$match:{ts:{$gte:new Date(Date.now()-3600000)}}},
  {$group:{_id:{ns:"$ns",op:"$op",queryHash:"$queryHash",
        planCacheKey:"$planCacheKey"},
    executions:{$sum:1},total_ms:{$sum:"$millis"},
    mean_ms:{$avg:"$millis"},max_ms:{$max:"$millis"},
    docs_examined:{$sum:"$docsExamined"}}},
  {$sort:{total_ms:-1}}, {$limit:30}
],{maxTimeMS:5000});
~~~

Missing queryHash/planCacheKey values collapse into a null group and can mix different shapes; inspect those records separately. Counts reflect profiler sampling/filters. queryHash is retained in the compared 8.0 schema; newer planCacheShapeHash is not required by this query.

Sources: [Profiler output](https://www.mongodb.com/docs/v8.0/reference/database-profiler/).

### Q09 — Profiler collection health

Check collection settings and retained coverage in each application database.

~~~javascript
db.getSiblingDB("appdb").getProfilingStatus();
db.getSiblingDB("appdb").system.profile.find(
  {},{ts:1}).sort({$natural:1}).limit(1);
db.getSiblingDB("appdb").system.profile.find(
  {},{ts:1}).sort({$natural:-1}).limit(1);
~~~

An absent/empty collection can mean profiling is disabled, nothing matched or records were overwritten. Never interpret that as proof of no slow operations.

Sources: [Profiler administration](https://www.mongodb.com/docs/v8.0/tutorial/manage-the-database-profiler/).

### Q10 — Workload and connection counters

Lightweight workload snapshot on each process.

~~~javascript
var s = db.adminCommand({serverStatus:1});
printjson({host:s.host,localTime:s.localTime,uptime:s.uptime,
  connections:s.connections,opcounters:s.opcounters,network:s.network,
  transactions:s.transactions,asserts:s.asserts});
~~~

opcounters are server operation categories, not one-to-one end-user SQL statements. Assert counters identify broad failures; use Q21 for retained messages.

Sources: [serverStatus](https://www.mongodb.com/docs/v8.0/reference/command/serverstatus/).

### Q11 — Database storage totals

Run for each selected application database; size scale is bytes.

~~~javascript
db.getSiblingDB("appdb").runCommand({dbStats:1,scale:1});
~~~

Storage sizes and document counts are estimates in some conditions. Avoid frequent estate-wide enumeration during an incident.

Sources: [dbStats](https://www.mongodb.com/docs/v8.0/reference/command/dbstats/).

### Q12 — Index usage

Run on each selected collection/member.

~~~javascript
db.getSiblingDB("appdb").orders.aggregate([
  {$indexStats:{}},
  {$project:{name:1,key:1,host:1,shard:1,accesses:1}},
  {$sort:{"accesses.ops":1}}
],{maxTimeMS:5000});
~~~

Usage resets on restart and index recreation/modification. Zero observed reads is not sufficient to drop a unique, TTL, constraint-related or infrequently used index.

Sources: [$indexStats](https://www.mongodb.com/docs/v8.0/reference/operator/aggregation/indexstats/).

### Q13 — WiredTiger cache pressure

Inspect the local storage engine without hardcoding changing WiredTiger subfields.

~~~javascript
var s = db.adminCommand({serverStatus:1});
printjson({host:s.host,uptime:s.uptime,
  cache:s.wiredTiger ? s.wiredTiger.cache : null});
~~~

Compare used/dirty cache gauges with configured maximum and eviction/read counters. Not available from mongos; field names vary by storage-engine version.

Sources: [serverStatus](https://www.mongodb.com/docs/v8.0/reference/command/serverstatus/).

### Q14 — Current maintenance operations

Find index builds and operations exposing progress.

~~~javascript
db.getSiblingDB("admin").aggregate([
  {$currentOp:{allUsers:true}},
  {$match:{$or:[{"command.createIndexes":{$exists:true}},
               {progress:{$exists:true}}]}},
  {$project:{host:1,opid:1,ns:1,secs_running:1,msg:1,progress:1}},
  {$limit:50}
],{maxTimeMS:5000});
~~~

Progress is not supplied for every operation. Inspect the phase description rather than treating a missing denominator as zero percent.

Sources: [$currentOp](https://www.mongodb.com/docs/v8.0/reference/operator/aggregation/currentop/).

### Q15 — Durability and journal counters

Inspect local journal and flow-control metrics.

~~~javascript
var s = db.adminCommand({serverStatus:1});
printjson({host:s.host,uptime:s.uptime,
  journal:s.wiredTiger ? s.wiredTiger.log : null,
  flowControl:s.flowControl});
~~~

Interpret journaling counters as storage-engine activity. They do not certify replication durability or a particular client writeConcern.

Sources: [serverStatus](https://www.mongodb.com/docs/v8.0/reference/command/serverstatus/).

### Q16 — Collection latency counters

Collection storage and cumulative read/write latency.

~~~javascript
db.getSiblingDB("appdb").orders.aggregate([
  {$collStats:{latencyStats:{histograms:true},storageStats:{scale:1}}},
  {$project:{ns:1,host:1,shard:1,localTime:1,latencyStats:1,
    "storageStats.size":1,"storageStats.storageSize":1,
    "storageStats.totalIndexSize":1,"storageStats.count":1}}
],{maxTimeMS:5000});
~~~

latency is cumulative microseconds; interval mean = delta(latency)/delta(ops). Sharded results can contain one record per shard. Storage statistics do not apply to ordinary views.

Sources: [$collStats](https://www.mongodb.com/docs/v8.0/reference/operator/aggregation/collstats/).

### Q17 — Plan cache inspection

Inspect cached plans for a selected collection.

~~~javascript
db.getSiblingDB("appdb").orders.aggregate([
  {$planCacheStats:{}},
  {$project:{host:1,shard:1,planCacheKey:1,queryHash:1,
    isActive:1,works:1,timeOfCreation:1,cachedPlan:1}},
  {$limit:30}
],{maxTimeMS:5000});
~~~

Plan-cache entries are diagnostic state, not execution history. Classic and slot-based engine plan details differ; do not clear the cache as a collection step.

Sources: [$planCacheStats](https://www.mongodb.com/docs/v8.0/reference/operator/aggregation/plancachestats/).

### Q18 — Replica health and apply lag

Run directly on a replica-set member.

~~~javascript
var r = db.adminCommand({replSetGetStatus:1});
var p = (r.members || []).find(m => m.stateStr === "PRIMARY");
printjson({set:r.set,date:r.date,myState:r.myState,
  members:(r.members || []).map(m => ({
    name:m.name,state:m.stateStr,health:m.health,optimeDate:m.optimeDate,
    heartbeatError:m.lastHeartbeatMessage,
    approximateLagSeconds:p && p.optimeDate && m.optimeDate
      ? (p.optimeDate-m.optimeDate)/1000 : null
  }))});
~~~

Lag is a rough optime difference from this member’s view, not end-to-end application freshness. A missing primary, unknown health or stale heartbeat needs separate handling. Arbiters have no useful data apply lag.

Sources: [replSetGetStatus](https://www.mongodb.com/docs/v8.0/reference/command/replsetgetstatus/).

### Q19 — Oplog retention window

Read endpoint timestamps in the local capped oplog, without scanning it.

~~~javascript
var o = db.getSiblingDB("local").getCollection("oplog.rs");
var a = o.find({},{ts:1}).sort({$natural:1}).limit(1).toArray()[0];
var b = o.find({},{ts:1}).sort({$natural:-1}).limit(1).toArray()[0];
printjson({oldest:a ? a.ts : null,newest:b ? b.ts : null,
  windowSeconds:a && b ? b.ts.getHighBits()-a.ts.getHighBits() : null});
~~~

This is the locally retained replication window, not replica lag. Compare Q18 lag with this window to identify resync risk. Restricted managed tiers may deny local oplog access.

Sources: [replSetGetStatus](https://www.mongodb.com/docs/v8.0/reference/command/replsetgetstatus/), [Oplog](https://www.mongodb.com/docs/v8.0/core/replica-set-oplog/).

### Q20 — Optional query statistics

Optional eligible Atlas deployments only; first verify the exact minor release and privileges.

~~~javascript
db.getSiblingDB("admin").aggregate([
  {$queryStats:{}}, {$limit:20}
],{maxTimeMS:5000});
~~~

Returns raw normalized-shape runtime records. The unstable schema and in-memory retention make this unsuitable as a cross-version fixed contract. This small sample is not a top-slowest ranking.

Sources: [$queryStats](https://www.mongodb.com/docs/v8.0/reference/operator/aggregation/querystats/).

## Internal server logs and historical events

### Recommended logging baseline

Keep profiler collection separate from process logging. Profiler levels are database-scoped, while slowms and sampleRate changes affect the process globally; a profiler filter changes how slowms/sampleRate are applied. Capture the existing settings first. On mongos there is no database profiler collection; slow-operation process logs are the relevant path.

For a controlled diagnostic window on a selected mongod/database, an operator can use the following configuration change, after assessing overhead and restoring the prior settings afterwards:

~~~javascript
// CONFIGURATION CHANGE: example only, not part of read-only polling.
db.getSiblingDB("appdb").getProfilingStatus();
db.getSiblingDB("appdb").setProfilingLevel(1,{slowms:500,sampleRate:0.1});
~~~

This records a sample, so absence of a record proves little. Avoid continuous level 2 collection. Slow-operation selection and elapsed duration are not identical across releases; the 8.0 documentation describes working time excluding lock/flow-control waiting. Keep structured process logs with deliberate rotation/retention if complete incident history is required. Reading logs through the DB does not create missing history. Sources: [Profiler administration](https://www.mongodb.com/docs/v8.0/tutorial/manage-the-database-profiler/), [profile command](https://www.mongodb.com/docs/v8.0/reference/command/profile/).


### Q21 — Recent internal errors and warnings

Read the process RAM log, retaining unparsable/truncated entries for investigation.

~~~javascript
var r = db.adminCommand({getLog:"global"});
var events = r.log.map(line => {
  try { return JSON.parse(line); }
  catch (e) { return {unparsed:true,raw:line}; }
});
events.filter(e => e.unparsed || ["E","F","W"].includes(e.s))
  .slice(-100).forEach(e => printjson(e));
~~~

getLog retains only the most recent 1,024 events and truncates long events; JSON parsing can fail. totalLinesWritten is not a durable cursor. Polling can duplicate or lose records; this is neither a full server logfile nor a complete client-error journal.

Sources: [getLog](https://www.mongodb.com/docs/v8.0/reference/command/getlog/).

### Q22 — Recent slow-operation log entries

Inspect recent messages that include a slow-query marker or duration.

~~~javascript
var r = db.adminCommand({getLog:"global"});
var events = r.log.map(line => {
  try { return JSON.parse(line); }
  catch (e) { return {unparsed:true,raw:line}; }
});
events.filter(e => !e.unparsed &&
  (e.msg === "Slow query" ||
   (e.attr && typeof e.attr.durationMillis === "number" &&
    e.attr.durationMillis >= 500)))
  .slice(-100).forEach(e => printjson(e));
~~~

Message structure and selection differ by release. Duration-bearing non-query events can match; inspect component/message and use Q07 for profiler executions. Buffer turnover can erase the incident before polling.

Sources: [getLog](https://www.mongodb.com/docs/v8.0/reference/command/getlog/), [Profiler output](https://www.mongodb.com/docs/v8.0/reference/database-profiler/).

## Deeper diagnosis and rollout

Start Q01, Q10, Q18 and Q21; add Q02/Q05 during symptoms. A starting cadence is 15–60 seconds for small counter snapshots, 5–15 seconds for temporary incident sampling, and 5–15 minutes for storage/index checks. Benchmark overhead on your workload.

For a particular query, use explain("queryPlanner") first. explain("executionStats") executes the read workload and can be expensive; apply representative bounds and an appropriate maxTimeMS. It is an investigation step, not a scrape target. [Explain helper](https://www.mongodb.com/docs/v8.0/reference/method/db.collection.explain/).

Validate with a representative slow read, an open transaction and a controlled lock-contention scenario in non-production. Verify profiler eligibility, time windows, capped rollover, direct-member permissions, integer handling and restart detection. Add a narrow internal collection for retained snapshots if historical analysis must stay inside MongoDB; define TTL indexes and redact command payloads deliberately. Internal collection writes require a separate writer role.

## References

The links beside each query are the primary documentation used. Core source index:

- [$currentOp](https://www.mongodb.com/docs/v8.0/reference/operator/aggregation/currentop/)
- [serverStatus](https://www.mongodb.com/docs/v8.0/reference/command/serverstatus/)
- [Profiler administration](https://www.mongodb.com/docs/v8.0/tutorial/manage-the-database-profiler/)
- [Profiler output](https://www.mongodb.com/docs/v8.0/reference/database-profiler/)
- [getLog](https://www.mongodb.com/docs/v8.0/reference/command/getlog/)
- [$collStats](https://www.mongodb.com/docs/v8.0/reference/operator/aggregation/collstats/)
- [$indexStats](https://www.mongodb.com/docs/v8.0/reference/operator/aggregation/indexstats/)
- [replSetGetStatus](https://www.mongodb.com/docs/v8.0/reference/command/replsetgetstatus/)
- [getCmdLineOpts](https://www.mongodb.com/docs/v8.0/reference/command/getcmdlineopts/)
- [dbStats](https://www.mongodb.com/docs/v8.0/reference/command/dbstats/)
- [$planCacheStats](https://www.mongodb.com/docs/v8.0/reference/operator/aggregation/plancachestats/)
- [$queryStats](https://www.mongodb.com/docs/v8.0/reference/operator/aggregation/querystats/)
- [explain helper](https://www.mongodb.com/docs/v8.0/reference/method/db.collection.explain/)
