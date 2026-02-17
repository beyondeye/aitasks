---
name: Android Best Practices
description: Check lifecycle awareness, coroutines, Compose patterns, and memory management
environment: [android, kotlin]
---

## Review Instructions

### Lifecycle Awareness
- Flag View or UI references accessed after `onDestroyView()` — store view references in `onCreateView()` and null them in `onDestroyView()`
- Check that coroutines or callbacks don't outlive their lifecycle owner — use `viewLifecycleOwner.lifecycleScope` in Fragments, not `lifecycleScope`
- Look for Activity/Fragment references leaked through callbacks, listeners, or singletons — use weak references or lifecycle-aware components
- Flag `onActivityResult` or other deprecated lifecycle methods — use Activity Result API (`registerForActivityResult`)
- Check that observers are registered with the correct lifecycle owner (Fragment should use `viewLifecycleOwner`, not `this`)
- Look for work started in `onCreate` that should be in `onStart` or `onResume` (and vice versa)

### Coroutines and Threading
- Flag blocking calls on the main thread: synchronous network requests, heavy disk I/O, or database queries without `withContext(Dispatchers.IO)`
- Look for `GlobalScope.launch` — use `viewModelScope`, `lifecycleScope`, or a custom scope with proper cancellation
- Check for missing `withContext(Dispatchers.IO)` around disk/network operations inside coroutines launched on Main dispatcher
- Flag unstructured concurrency: fire-and-forget coroutines that aren't tied to a lifecycle scope
- Look for `runBlocking` on the main thread — this defeats the purpose of coroutines and causes ANRs
- Check that exceptions in coroutines are handled (use `CoroutineExceptionHandler` or try/catch within launch blocks)

### Jetpack Compose
- Flag state objects created inside `@Composable` functions without `remember` — they will be recreated on every recomposition
- Look for expensive computations in composable functions — use `remember` with appropriate keys or `derivedStateOf`
- Check that side effects are in proper effect handlers: `LaunchedEffect` for coroutines, `DisposableEffect` for cleanup, `SideEffect` for non-suspend side effects
- Flag mutable state not using `mutableStateOf` or `mutableStateListOf` — Compose won't observe plain `var` changes
- Look for unnecessary recompositions: passing unstable types (Lists, lambda captures) without stabilization
- Check that `key()` is used for items in `LazyColumn`/`LazyRow` to preserve state during reordering

### Memory and Performance
- Flag Bitmap loading without downsampling — use `BitmapFactory.Options` with `inSampleSize` or Coil/Glide for image loading
- Look for `Serializable` on frequently-parceled objects — use `Parcelable` (or `@Parcelize` in Kotlin) for better performance
- Check for large object graphs stored in `savedInstanceState` — keep saved state under 500KB, use ViewModel or persistent storage for large data
- Flag missing `RecyclerView.ViewHolder` patterns or manual view inflation in adapters
- Look for unnecessary wake locks, location updates, or sensor listeners that aren't released when not needed
- Check that WorkManager is used for deferrable background work instead of foreground services or `AlarmManager` hacks
