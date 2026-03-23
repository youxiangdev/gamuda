TODO.md
1. Add metadata filtering for document retrieving
2. Revisit the implementation on document agent and data_analysis, there are still a lot of improvement such as 
    1. For document, instead of relying on one agent to perform, searching, revaluate the gap, split it into multiple agent to do. To increase the reliability
    2. For Data, test with more testing data to find out the optimize solutions for data agent.
    3. For router, add more context on the real business rules.
    4. For data ingestion, currently pdf and csv is separated, this is the first idea as I am thinking csv purely for analytic only, but after I built on the agent, I reliaze I should ingest the csv into data chunk as well, to increase the retrieval quality.
    5. Citation enhancement, current citation direct show in response, which is not good in ux perspective, it should be a clickable link direct show which column, which section showing it.
    6. Explore other model to find the optimal model and solution.
    7. The production env having some latency I would need to find out, might be server, or code issue, but locally is working fine.
    8. Currently, all the token, pricing is log and calculated, but because of lacking of time, I am not able to complete the cost per query requirement.
    9. Code level implementation might not be the best practice for production ready and enough clarity (comment, and etc), as not enough time for this.
    10. test case is not implemented to test on the api, query due to insufficient of time.
    11. the current evaluation can considered not completed as well. can create a proper documentation and script for this.