package org.sandag.abm.active.sandag;

import java.util.*;
import org.sandag.abm.active.*;

public abstract class SandagBikePathAlternativeListGenerationConfiguration implements PathAlternativeListGenerationConfiguration<SandagBikeNode,SandagBikeEdge,SandagBikeTraversal>
{
    protected Map<String,String> propertyMap;
    protected PropertyParser propertyParser;
    protected final String PROPERTIES_SAMPLE_MAXCOST = "active.sample.maxcost";
    protected final String PROPERTIES_SAMPLE_RANDOM_SPREADS = "active.sample.random.spreads";
    protected final String PROPERTIES_SAMPLE_RANDOM_SEEDED = "active.pathsize.random.seeded";
    protected final String PROPERTIES_SAMPLE_DISTANCE_BREAKS = "active.sample.distance.breaks";
    protected final String PROPERTIES_SAMPLE_PATHSIZES = "active.sample.pathsizes";
    protected final String PROPERTIES_SAMPLE_COUNT_MIN = "active.sample.count.min";
    protected final String PROPERTIES_SAMPLE_COUNT_MAX = "active.sample.count.max";
    
    protected String PROPERTIES_MAXDIST_ZONE;
    
    protected Map<Integer,Map<Integer,Double>> nearbyZonalDistanceMap;
    protected Map<Integer,Integer> zonalCentroidIdMap;
    protected Network<SandagBikeNode,SandagBikeEdge,SandagBikeTraversal> network;
    
    public SandagBikePathAlternativeListGenerationConfiguration(Map<String,String> propertyMap, Network<SandagBikeNode,SandagBikeEdge,SandagBikeTraversal> network)
    {
        this.propertyMap = propertyMap;
        this.propertyParser = new PropertyParser(propertyMap);
        this.nearbyZonalDistanceMap = null;
        this.zonalCentroidIdMap = null;
        this.network = network;
    }
    
    @Override
    public Network<SandagBikeNode, SandagBikeEdge, SandagBikeTraversal> getNetwork()
    {
        return network;
    }
    
    static class SandagBikeDistanceEvaluator implements EdgeEvaluator<SandagBikeEdge>
    {            
        public double evaluate(SandagBikeEdge edge) { return edge.distance; }
    }
    
    static class ZeroTraversalEvaluator implements TraversalEvaluator<SandagBikeTraversal>
    {
        public double evaluate(SandagBikeTraversal traversal) { return 999 * ( traversal.thruCentroid ? 1 : 0 ); }
    }
    
    @Override
    public EdgeEvaluator<SandagBikeEdge> getEdgeLengthEvaluator()
    {
        return new SandagBikeDistanceEvaluator();
    }

    @Override
    public EdgeEvaluator<SandagBikeEdge> getEdgeCostEvaluator()
    {
        final class SandagBikeEdgeCostEvaluator implements EdgeEvaluator<SandagBikeEdge>
        {
            public double evaluate(SandagBikeEdge edge) { return edge.cost; }
        }
        
        return new SandagBikeEdgeCostEvaluator();
    }

    @Override
    public TraversalEvaluator<SandagBikeTraversal> getTraversalCostEvaluator()
    {
        final class SandagBikeTraversalCostEvaluator implements TraversalEvaluator<SandagBikeTraversal>
        {
            public double evaluate(SandagBikeTraversal traversal) { return traversal.cost; }
        }
        
        return new SandagBikeTraversalCostEvaluator();
    }

    @Override
    public double getMaxCost()
    {
        return Double.parseDouble(propertyMap.get(PROPERTIES_SAMPLE_MAXCOST));
    }

    @Override
    public double[] getRandomizationSpreads()
    {
        return propertyParser.parseDoublePropertyArray(PROPERTIES_SAMPLE_RANDOM_SPREADS);
    }

    @Override
    public double[] getSampleDistanceBreaks()
    {
        return propertyParser.parseDoublePropertyArray(PROPERTIES_SAMPLE_DISTANCE_BREAKS);
    }

    @Override
    public double[] getSamplePathSizes()
    {
        return propertyParser.parseDoublePropertyArray(PROPERTIES_SAMPLE_PATHSIZES);
    }
    
    @Override
    public double[] getSampleMinCounts()
    {
        return propertyParser.parseDoublePropertyArray(PROPERTIES_SAMPLE_COUNT_MIN);
    }
    
    @Override
    public double[] getSampleMaxCounts()
    {
        return propertyParser.parseDoublePropertyArray(PROPERTIES_SAMPLE_COUNT_MAX);
    }

    @Override
    public boolean isRandomCostSeeded()
    {
        return Boolean.parseBoolean(propertyMap.get(PROPERTIES_SAMPLE_RANDOM_SEEDED));
    }

    @Override
    public Map<Integer, Map<Integer, Double>> getNearbyZonalDistanceMap()
    {
        if ( nearbyZonalDistanceMap == null ) {
            nearbyZonalDistanceMap = new HashMap<>();
            ShortestPathStrategy<SandagBikeNode> sps = new ParallelSingleSourceDijkstra<SandagBikeNode>(new RepeatedSingleSourceDijkstra<SandagBikeNode, SandagBikeEdge, SandagBikeTraversal>(network, new SandagBikeDistanceEvaluator(), new ZeroTraversalEvaluator()), ParallelSingleSourceDijkstra.ParallelMethod.QUEUE);
            if ( zonalCentroidIdMap == null ) {
                createZonalCentroidIdMap();
            }
            Set<SandagBikeNode> nodes = new HashSet<>();
            Map<SandagBikeNode,Integer> inverseZonalCentroidMap = new HashMap<>();
            SandagBikeNode n;
            for ( int zone : zonalCentroidIdMap.keySet() ) {
                n = network.getNode(zonalCentroidIdMap.get(zone));
                nodes.add(n);
                inverseZonalCentroidMap.put(n, zone);
            }
            System.out.println("Calculating nearby Zonal Distance Map");
            ShortestPathResultSet<SandagBikeNode> resultSet = sps.getShortestPaths(nodes, nodes, Double.parseDouble(propertyMap.get(PROPERTIES_MAXDIST_ZONE)));
            int originZone, destinationZone;
            for (NodePair<SandagBikeNode> odPair : resultSet) {
                    originZone = inverseZonalCentroidMap.get(odPair.getFromNode());
                    destinationZone = inverseZonalCentroidMap.get(odPair.getToNode());
                    if ( ! nearbyZonalDistanceMap.containsKey(originZone) ) {
                        nearbyZonalDistanceMap.put(originZone, new HashMap<Integer,Double>() );
                    }
                    nearbyZonalDistanceMap.get(originZone).put(destinationZone,resultSet.getShortestPathResult(odPair).getCost());
            }
        }
        return nearbyZonalDistanceMap;
    }
    
    @Override
    public Map<Integer, Integer> getZonalCentroidIdMap()
    {
        if (zonalCentroidIdMap == null) {
            createZonalCentroidIdMap();
        }
        
        return zonalCentroidIdMap;
    }
    
    protected abstract void createZonalCentroidIdMap();
    
}
